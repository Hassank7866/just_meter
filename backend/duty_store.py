"""Source coverage, historical duty lookup, and audited officer resolution."""
from copy import deepcopy
from datetime import timedelta

from sqlalchemy import func, select

from .config import get_local_now
from .db_models import AuditEvent, DutyCoverage, DutyReview, Evidence, RiskAssessment, RiskTask, Sighting, Vehicle, VimsSource, VimsSyncRun
from .db_records import normalized
from .duty_verification import finish, merge_duty, moment, rule, verify_snapshot
from .access import scoped_source_records


class DutyStore:
    def attach_duty_to_evidence(self, recognition_id, duty):
        with self._lock as session:
            evidence = self.get_evidence_for_recognition(recognition_id)
            if evidence:
                item = session.scalar(select(Evidence).where(Evidence.record_key == evidence["evidence_id"]))
                item.payload = item.payload | {"duty_verification": deepcopy(duty)}

    def duty_observation(self, sighting_id):
        with self._lock as session:
            sighting = session.get(Sighting, sighting_id)
            if sighting is None:
                return None
            review = session.scalar(select(DutyReview).where(DutyReview.sighting_id == sighting.id))
            return {"id": sighting.id, "current": deepcopy(sighting.payload), "review": {
                "actor": review.reviewed_by, "at": moment(review.reviewed_at).isoformat(),
                "notes": review.notes, "original": review.original, "decision": review.decision} if review else None}

    def duty_coverage(self):
        with self._lock as session:
            rows = []
            for source in session.scalars(select(VimsSource).order_by(VimsSource.name)):
                coverage = session.scalar(select(DutyCoverage).where(DutyCoverage.source_id == source.id))
                rows.append({"source": source.name, "revision": source.revision,
                    "confirmed": bool(coverage and coverage.source_revision == source.revision),
                    "coverage": {"valid_from": moment(coverage.valid_from).isoformat(),
                        "valid_until": moment(coverage.valid_until).isoformat(), "max_age_hours": coverage.max_age_hours,
                        "source_revision": coverage.source_revision, "confirmed_by": coverage.confirmed_by,
                        "confirmed_at": moment(coverage.confirmed_at).isoformat()} if coverage else None})
            return rows

    def confirm_duty_coverage(self, name, body, actor):
        with self._lock as session:
            source = session.scalar(select(VimsSource).where(VimsSource.name == name))
            if source is None:
                raise LookupError("VIMS source not found")
            if source.revision != body.expected_revision:
                raise ValueError("Source revision changed; refresh and review the source records")
            coverage = session.scalar(select(DutyCoverage).where(DutyCoverage.source_id == source.id))
            if coverage is None:
                coverage = DutyCoverage(source_id=source.id)
                session.add(coverage)
            coverage.source_revision = source.revision
            coverage.valid_from, coverage.valid_until = body.valid_from, body.valid_until
            coverage.max_age_hours = body.max_age_hours
            coverage.confirmed_at, coverage.confirmed_by = get_local_now(), actor
            session.add(AuditEvent(occurred_at=get_local_now(), actor=actor, action="DUTY_COVERAGE_CONFIRMED",
                entity=source.name, details=body.model_dump(mode="json")))
        return self.duty_coverage()

    def verify_vehicle_duty(self, plate, observed_at, camera_area):
        when = moment(observed_at)
        result = {"observed_at": when.isoformat(), "camera_area": camera_area,
                  "source": None, "source_revision": None, "assignment": None, "duty_slip": None, "rules": []}

        def uncertain(message):
            result["rules"] = [rule("DUTY_SOURCE", "REVIEW", message)]
            return finish(result)

        with self._lock as session:
            vehicle = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == normalized(plate)))
            if vehicle is None or vehicle.vims_source_id is None:
                return uncertain("No synchronized duty source is linked to this vehicle")
            source = session.get(VimsSource, vehicle.vims_source_id)
            result.update(source=source.name, source_revision=source.revision)
            coverage = session.scalar(select(DutyCoverage).where(DutyCoverage.source_id == source.id))
            if coverage is None or coverage.source_revision != source.revision:
                return uncertain("Administrator must confirm complete duty coverage for this source revision")
            if not moment(coverage.valid_from) <= when < moment(coverage.valid_until):
                return uncertain("Detection is outside the source's confirmed coverage period")
            runs = list(session.scalars(select(VimsSyncRun).where(VimsSyncRun.source_id == source.id,
                VimsSyncRun.status == "APPLIED", VimsSyncRun.exported_at <= when).order_by(VimsSyncRun.exported_at, VimsSyncRun.id)))
            if not runs:
                return uncertain("No source export at or before the detection time; future records cannot establish past authorization")
            latest = runs[-1]
            if when - moment(latest.exported_at) > timedelta(hours=coverage.max_age_hours):
                return uncertain("The source export is too old for this detection's confirmed freshness limit")
            records = {kind: {} for kind in ("departments", "vehicles", "drivers", "assignments", "duty_slips")}
            for run in runs:
                for change in run.changes:
                    records[change["kind"]][change["external_id"]] = deepcopy(change["after"])
            records = scoped_source_records(session, records, source.id)
            if vehicle.vims_external_id not in records["vehicles"]:
                return uncertain("Vehicle was not present in the source snapshot at capture time")
            snapshot = {"source": source.name, "source_revision": len(runs),
                        "exported_at": moment(latest.exported_at).isoformat(), "records": records}
            result = verify_snapshot(snapshot, vehicle.vims_external_id, when, camera_area)
            result["source_run_id"] = latest.id
            result["coverage"] = {"source_revision": coverage.source_revision,
                "confirmed_by": coverage.confirmed_by, "confirmed_at": moment(coverage.confirmed_at).isoformat(),
                "valid_from": moment(coverage.valid_from).isoformat(), "valid_until": moment(coverage.valid_until).isoformat(),
                "max_age_hours": coverage.max_age_hours}
            return result

    def duty_observations(self, pending=True, limit=100, offset=0):
        # JSON snapshots are portable between PostgreSQL and isolated SQLite tests.
        with self._lock as session:
            sightings = session.scalars(select(Sighting).order_by(Sighting.id.desc()))
            rows = []
            for sighting in sightings:
                duty = sighting.payload.get("duty_verification")
                if not duty or (pending and not duty.get("review_required")):
                    continue
                rows.append({"id": sighting.id, "recognition_id": sighting.payload.get("recognition_id"),
                    "plate_number": sighting.payload.get("plate_number"), "timestamp": sighting.payload.get("timestamp"),
                    "camera_area": sighting.payload.get("camera_area"), "status": sighting.status,
                    "image": sighting.payload.get("image"), "duty_verification": deepcopy(duty)})
            return {"total": len(rows), "items": rows[offset:offset + limit]}

    def review_vehicle_duty(self, sighting_id, body, actor):
        with self._lock as session:
            sighting = session.get(Sighting, sighting_id)
            if sighting is None:
                raise LookupError("Observation not found")
            if session.scalar(select(DutyReview.id).where(DutyReview.sighting_id == sighting.id)):
                raise ValueError("This duty observation has already received a final officer decision")
            original = deepcopy(sighting.payload)
            duty = deepcopy(original.get("duty_verification"))
            if not duty or not duty.get("reviewable") or not duty.get("duty_slip"):
                raise ValueError("This observation needs source correction, not destination/purpose confirmation")
            for name, field in (("DUTY_DESTINATION", "destination"), ("DUTY_PURPOSE", "purpose")):
                choice = getattr(body, field)
                if name in duty["reviewable"] and choice == "UNRESOLVED":
                    raise ValueError("Resolve every destination/purpose question before submitting a final decision")
                if name not in duty["reviewable"] and choice != "UNRESOLVED":
                    raise ValueError("Only pending destination/purpose rules can be resolved")
                for entry in duty["rules"]:
                    if entry["rule_id"] == name and entry["outcome"] == "REVIEW":
                        entry.update(outcome="PASS" if choice == "MATCH" else "FAIL",
                            message=f"Officer confirmed {field} {'matches' if choice == 'MATCH' else 'does not match'} the approved duty: {body.notes}",
                            criteria="" if choice == "MATCH" else "UNAUTHORIZED_DESTINATION" if field == "destination" else "NO_VALID_DUTY_SLIP")
            duty = finish(duty)
            duty["review"] = {"actor": actor, "at": get_local_now().isoformat(), **body.model_dump()}
            compliance = merge_duty(original["base_compliance"], duty)
            vehicle = session.get(Vehicle, sighting.vehicle_id)
            policy, risk = self._score_current_risk(session, compliance, vehicle.normalized_plate if vehicle else sighting.normalized_plate,
                moment(sighting.observed_at), {"risk_context": original.get("risk_context", "")})
            assessment = session.scalar(select(RiskAssessment).where(RiskAssessment.sighting_id == sighting.id))
            previous_risk = deepcopy(assessment.result) if assessment else None
            if assessment is None:
                self._persist_risk(session, sighting, policy, risk)
            else:
                assessment.policy_id, assessment.assessed_at = policy.id, get_local_now()
                assessment.score, assessment.level, assessment.result = risk["risk_score"], risk["risk_level"], risk
                task = session.scalar(select(RiskTask).where(RiskTask.assessment_id == assessment.id))
                if risk["recommended_action"] != "NONE":
                    if task is None:
                        task = RiskTask(assessment_id=assessment.id)
                        session.add(task)
                    task.priority, task.assigned_role = risk["notification_priority"], risk["escalation_role"]
                    task.recommended_action, task.status = risk["recommended_action"], "OPEN"
                    task.acknowledged_by = task.acknowledged_at = None
            sighting.status = compliance["status"]
            sighting.violation_id = f"VIOL-{sighting.record_key}" if sighting.status == "VIOLATION" else None
            prior = session.scalar(select(func.count()).select_from(Sighting).where(
                Sighting.vehicle_id == sighting.vehicle_id, Sighting.status == "VIOLATION",
                Sighting.observed_at < sighting.observed_at)) or 0
            import json
            sighting.payload = original | compliance | risk | {"decision_rules": json.dumps(compliance["rules"]),
                "risk_factors": json.dumps(risk["risk_factors"]), "violation_id": sighting.violation_id or "",
                "violation_count": prior + bool(sighting.violation_id)}
            review = DutyReview(sighting_id=sighting.id, reviewed_by=actor, reviewed_at=get_local_now(),
                notes=body.notes, original=original | {"previous_risk_assessment": previous_risk},
                decision={"compliance": compliance, "risk": risk})
            session.add(review)
            evidence = self.get_evidence_for_recognition(original.get("recognition_id", ""))
            if evidence:
                item = session.scalar(select(Evidence).where(Evidence.record_key == evidence["evidence_id"]))
                item.sighting_id = sighting.id
                item.payload = item.payload | {"duty_verification": duty}
                if sighting.violation_id:
                    item.payload = item.payload | {"related_violation_id": sighting.violation_id}
                    if item.case_status == "UNASSIGNED":
                        item.case_status = "ATTACHED_TO_VIOLATION"
                        item.payload = item.payload | {"case_status": item.case_status}
            session.add(AuditEvent(occurred_at=get_local_now(), actor=actor, action="DUTY_REVIEW_COMPLETED",
                entity=str(sighting.id), department_id=sighting.department_id, details={"before_status": original.get("status"),
                    "after_status": sighting.status, "decision": body.model_dump(), "risk_policy_version": policy.version}))
            if sighting.status == "VIOLATION":
                self._ensure_challan_draft(session, sighting, actor)
            return {"id": sighting.id, "status": sighting.status, "duty_verification": duty, "risk": risk}
