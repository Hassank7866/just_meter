"""Live vehicle read model. Relationships, never plate guesses, own history."""
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import func, literal, or_, select, union_all

from .db_models import (Challan, ChallanEvent, Department, Detection, DutyReview, DutySlip, Evidence, Recognition, VehicleEvent,
                        RiskAssessment, RiskTask, Sighting, Vehicle,
                        VehicleAssignment, VimsSource, VimsSyncRun)
from .db_records import normalized
from .duty_verification import moment, within
from .access import scoped_source_records


def iso(value):
    return moment(value).isoformat() if value else None


class DigitalTwinStore:
    def twin_reference_id(self, *, plate=None, sighting_key=None, evidence_key=None):
        with self._lock as session:
            if sighting_key:
                return session.scalar(select(Sighting.vehicle_id).where(Sighting.record_key == sighting_key))
            if evidence_key:
                evidence = session.scalar(select(Evidence).where(Evidence.record_key == evidence_key))
                if evidence is None:
                    return None
                if evidence.sighting_id is not None:
                    sighting = session.get(Sighting, evidence.sighting_id)
                    return sighting.vehicle_id if sighting else None
                if evidence.recognition_id is not None:
                    return session.scalar(select(Sighting.vehicle_id).join(Detection).where(
                        Detection.recognition_id == evidence.recognition_id))
                return None
            return self.twin_vehicle_id(plate) if plate else None

    def twin_vehicle_id(self, plate):
        with self._lock as session:
            return session.scalar(select(Vehicle.id).where(Vehicle.normalized_plate == normalized(plate)))

    def twin_vehicles(self, query="", limit=30, offset=0):
        with self._lock as session:
            statement = select(Vehicle)
            if query.strip():
                term = normalized(query)
                conditions = [Vehicle.vehicle_id.icontains(query.strip(), autoescape=True)]
                if term:
                    conditions.append(Vehicle.normalized_plate.contains(term, autoescape=True))
                statement = statement.where(or_(*conditions))
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            rows = session.scalars(statement.order_by(Vehicle.plate_number, Vehicle.id).limit(limit).offset(offset))
            return {"total": total, "items": [{"id": v.id, "plate_number": v.plate_number,
                "vehicle_id": v.vehicle_id, "active": v.active} for v in rows]}

    def _twin_source(self, session, vehicle, when):
        """Replay source changes; future imports must not rewrite earlier context."""
        source = session.get(VimsSource, vehicle.vims_source_id) if vehicle.vims_source_id else None
        if source is None:
            return {"source": None, "exported_at": None, "vehicle": None,
                    "assignments": [], "duty_slips": [], "warnings": ["No synchronized VIMS source is linked to this vehicle."]}
        records = {kind: {} for kind in ("vehicles", "departments", "drivers", "assignments", "duty_slips")}
        latest = None
        runs = session.scalars(select(VimsSyncRun).where(VimsSyncRun.source_id == source.id,
            VimsSyncRun.status == "APPLIED", VimsSyncRun.exported_at <= when)
            .order_by(VimsSyncRun.exported_at, VimsSyncRun.id))
        for run in runs:
            latest = run
            for change in run.changes:
                records[change["kind"]][change["external_id"]] = deepcopy(change["after"])
        records = scoped_source_records(session, records, source.id)
        registry = records["vehicles"].get(vehicle.vims_external_id)
        assignments = [a for a in records["assignments"].values()
                       if a["vehicle_external_id"] == vehicle.vims_external_id
                       and a["status"] == "ACTIVE" and within(a, when)]
        for assignment in assignments:
            assignment["driver"] = records["drivers"].get(assignment["driver_external_id"])
            assignment["department"] = records["departments"].get(assignment["department_external_id"])
        ids = {a["external_id"] for a in assignments}
        slips = [d for d in records["duty_slips"].values() if d["assignment_external_id"] in ids
                 and d["status"] == "ACTIVE" and within(d, when)]
        warnings = []
        if registry is None:
            warnings.append("Vehicle was not present in a source export at or before the selected time.")
        if len(assignments) > 1 or len(slips) > 1:
            warnings.append("Overlapping source records require officer review.")
        return {"source": source.name, "current_revision": source.revision,
                "source_run_id": latest.id if latest else None,
                "exported_at": iso(latest.exported_at) if latest else None,
                "age_hours": round((when - moment(latest.exported_at)).total_seconds() / 3600, 1) if latest else None,
                "vehicle": registry, "assignments": assignments, "duty_slips": slips, "warnings": warnings}

    def _twin_stream(self, vehicle_id):
        # Evidence can be linked directly or through recognition -> detection -> sighting.
        links = select(Sighting.id.label("sighting_id"), Sighting.observed_at,
                       Detection.recognition_id).outerjoin(Detection, Sighting.detection_id == Detection.id)
        links = links.where(Sighting.vehicle_id == vehicle_id).subquery()
        evidence = select(Evidence.id.label("id"), func.min(links.c.observed_at).label("at"),
                          literal("evidence").label("kind")).join(links, or_(
            Evidence.sighting_id == links.c.sighting_id,
            (Evidence.sighting_id.is_(None) & (Evidence.recognition_id == links.c.recognition_id))))
        evidence = evidence.group_by(Evidence.id)
        return union_all(
            select(Sighting.id.label("id"), Sighting.observed_at.label("at"), literal("sighting").label("kind"))
                .where(Sighting.vehicle_id == vehicle_id),
            select(RiskAssessment.id, RiskAssessment.assessed_at, literal("risk"))
                .join(Sighting).where(Sighting.vehicle_id == vehicle_id),
            select(DutyReview.id, DutyReview.reviewed_at, literal("duty_review"))
                .join(Sighting).where(Sighting.vehicle_id == vehicle_id),
            select(VehicleAssignment.id, VehicleAssignment.valid_from, literal("assignment"))
                .where(VehicleAssignment.vehicle_id == vehicle_id),
            select(DutySlip.id, DutySlip.valid_from, literal("duty_slip"))
                .join(VehicleAssignment).where(VehicleAssignment.vehicle_id == vehicle_id),
            evidence,
            select(ChallanEvent.id, ChallanEvent.occurred_at, literal("challan"))
                .join(Challan).where(Challan.vehicle_id == vehicle_id),
        ).subquery()

    def _twin_event(self, session, row):
        models = {"sighting": Sighting, "risk": RiskAssessment, "duty_review": DutyReview,
                  "assignment": VehicleAssignment, "duty_slip": DutySlip, "evidence": Evidence, "challan": ChallanEvent}
        item = session.get(models[row.kind], row.id)
        if row.kind == "challan":
            case = session.get(Challan, item.challan_id)
            data = {"case_id": case.id, "reference": case.reference, "action": item.action,
                    "actor": item.actor, "details": item.details, "current_status": case.status}
        elif row.kind == "sighting":
            data = deepcopy(item.payload) | {"id": item.id, "status": item.status}
            detection = session.get(Detection, item.detection_id) if item.detection_id else None
            recognition = session.get(Recognition, detection.recognition_id) if detection and detection.recognition_id else None
            event = session.get(VehicleEvent, recognition.event_id) if recognition and recognition.event_id else None
            data["capture"] = {"detection": deepcopy(detection.payload) if detection else None,
                               "recognition": deepcopy(recognition.payload) if recognition else None,
                               "event": deepcopy(event.payload) if event else None}
        elif row.kind == "risk":
            task = session.scalar(select(RiskTask).where(RiskTask.assessment_id == item.id))
            data = deepcopy(item.result) | {"score": item.score, "level": item.level,
                "policy_id": item.policy_id, "sighting_id": item.sighting_id,
                "task": {"id": task.id, "status": task.status, "priority": task.priority,
                    "assigned_role": task.assigned_role, "recommended_action": task.recommended_action,
                    "acknowledged_by": task.acknowledged_by, "acknowledged_at": iso(task.acknowledged_at)} if task else None}
        elif row.kind == "duty_review":
            data = {"sighting_id": item.sighting_id, "reviewed_by": item.reviewed_by,
                    "notes": item.notes, "original": item.original, "decision": item.decision}
        elif row.kind == "evidence":
            data = deepcopy(item.payload) | {"id": item.id, "review_status": item.review_status,
                                           "case_status": item.case_status}
        else:
            data = deepcopy(item.vims_payload or {}) | {"id": item.id, "status": item.status,
                "valid_from": iso(item.valid_from), "valid_until": iso(item.valid_until)}
        return {"id": row.id, "kind": row.kind, "at": iso(row.at), "data": data}

    def vehicle_digital_twin(self, vehicle_id, *, as_of=None, start=None, end=None,
                             limit=30, offset=0, camera_area=""):
        now = datetime.now(timezone.utc)
        when = moment(as_of) if as_of else now
        with self._lock as session:
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle is None:
                return None
            department = session.get(Department, vehicle.department_id) if vehicle.department_id else None
            registry = deepcopy(vehicle.payload) | {"id": vehicle.id, "plate_number": vehicle.plate_number,
                "vehicle_id": vehicle.vehicle_id, "active": vehicle.active,
                "department": department.name if department else None, "department_id": vehicle.department_id,
                "authorized_areas": vehicle.authorized_areas, "duty_schedule": vehicle.duty_schedule}
            source = self._twin_source(session, vehicle, when)
            duty = self.verify_vehicle_duty(vehicle.plate_number, when, camera_area)
            counts = dict(session.execute(select(Sighting.status, func.count()).where(
                Sighting.vehicle_id == vehicle.id).group_by(Sighting.status)).all())
            latest = session.scalar(select(Sighting).where(Sighting.vehicle_id == vehicle.id,
                Sighting.observed_at.is_not(None)).order_by(Sighting.observed_at.desc(), Sighting.id.desc()).limit(1))
            risk = session.scalar(select(RiskAssessment).join(Sighting).where(Sighting.vehicle_id == vehicle.id)
                .order_by(RiskAssessment.assessed_at.desc(), RiskAssessment.id.desc()).limit(1))
            open_tasks = session.scalar(select(func.count()).select_from(RiskTask).join(RiskAssessment).join(Sighting)
                .where(Sighting.vehicle_id == vehicle.id, RiskTask.status == "OPEN"))
            stream = self._twin_stream(vehicle.id)
            history = select(stream)
            if start:
                history = history.where(stream.c.at >= start)
            if end:
                history = history.where(stream.c.at <= end)
            total = session.scalar(select(func.count()).select_from(history.subquery()))
            rows = session.execute(history.order_by(stream.c.at.desc().nulls_last(), stream.c.kind, stream.c.id.desc())
                                   .limit(limit).offset(offset)).all()
            timeline = [self._twin_event(session, row) for row in rows]
            warnings = list(source["warnings"])
            if not vehicle.active:
                warnings.append("This vehicle is archived in the current registry.")
            if duty["status"] == "REVIEW":
                warnings.extend(r["message"] for r in duty["rules"] if r["outcome"] == "REVIEW")
            return {"generated_at": iso(now), "as_of": iso(when), "vehicle": registry,
                "source_context": source, "duty_verification": duty,
                "compliance": {"total_sightings": sum(counts.values()), "by_status": counts,
                               "total_violations": counts.get("VIOLATION", 0)},
                "latest_sighting": (deepcopy(latest.payload) | {"id": latest.id, "status": latest.status, "observed_at": iso(latest.observed_at)}) if latest else None,
                "risk": {"score": risk.score, "level": risk.level, "assessed_at": iso(risk.assessed_at),
                         "sighting_id": risk.sighting_id, "result": risk.result} if risk else None,
                "open_tasks": open_tasks, "warnings": list(dict.fromkeys(warnings)),
                "timeline": {"total": total, "limit": limit, "offset": offset, "items": timeline},
                "semantics": {"registry": "current", "source_context": "as_of_export",
                    "summary": "all_time_current_decisions", "timeline": "event_time_with_current_record_state",
                    "challans": "Persisted lifecycle events; payment collection is not integrated."}}
