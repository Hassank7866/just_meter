"""Transactional, versioned draft -> approval -> issuance -> appeal workflow."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from uuid import uuid4

from sqlalchemy import and_, func, or_, select

from .challan_pdf import render_issued_challan
from .config import get_local_now, settings
from .db_models import AuditEvent, Challan, ChallanEvent, Detection, Evidence, Sighting, Vehicle
from .db_records import normalized
from .duty_verification import moment
from .access import scoped_department
from fastapi import HTTPException

STATES = {"DRAFT", "APPROVED", "ISSUED", "APPEALED", "UPHELD", "CANCELLED", "REJECTED"}


def iso(value):
    return moment(value).isoformat() if value else None


def fingerprint(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ChallanStore:
    def _challan_history(self, session, sighting):
        if sighting.vehicle_id is None or sighting.observed_at is None or sighting.status != "VIOLATION":
            return []
        return list(session.scalars(select(Sighting).where(Sighting.vehicle_id == sighting.vehicle_id,
            Sighting.status == "VIOLATION", or_(Sighting.observed_at < sighting.observed_at,
            and_(Sighting.observed_at == sighting.observed_at, Sighting.id <= sighting.id)))
            .order_by(Sighting.observed_at, Sighting.id)))

    def _challan_log(self, session, case, actor, action, details):
        now = get_local_now()
        session.add(ChallanEvent(challan_id=case.id, occurred_at=now, actor=actor, action=action, details=details))
        session.add(AuditEvent(occurred_at=now, actor=actor, action="CHALLAN_" + action,
                               entity=case.reference, details=details, department_id=case.department_id))

    def _ensure_challan_draft(self, session, sighting, actor="system"):
        existing_id = session.scalar(select(Challan.__table__.c.id).where(Challan.__table__.c.sighting_id == sighting.id))
        if existing_id:
            return session.get(Challan, existing_id)
        history = self._challan_history(session, sighting)
        if len(history) < 4:
            return None
        now = get_local_now()
        case = Challan(reference=f"CHL-{now.year}-{uuid4().hex[:12].upper()}",
            department_id=sighting.department_id if all(row.department_id == sighting.department_id for row in history) else None,
            vehicle_id=sighting.vehicle_id, sighting_id=sighting.id, status="DRAFT", version=1,
            fine_amount=2500 + (len(history) - 4) * 1000, created_at=now, created_by=actor, prepared_by=actor, snapshot={})
        session.add(case)
        session.flush()
        case.snapshot = self._challan_snapshot(session, case)
        self._challan_log(session, case, actor, "CREATED", {"status": "DRAFT", "fine_amount": case.fine_amount,
            "sighting_id": sighting.id, "policy": "Prototype: 4th and later confirmed observations; 2500 + 1000 per additional observation"})
        return case

    def create_challan_draft(self, vehicle_id, actor):
        with self._lock as session:
            if session.get(Vehicle, vehicle_id) is None:
                raise LookupError("Vehicle not found")
            sighting = session.scalar(select(Sighting).where(Sighting.vehicle_id == vehicle_id,
                Sighting.status == "VIOLATION", Sighting.observed_at.is_not(None))
                .order_by(Sighting.observed_at.desc(), Sighting.id.desc()).limit(1))
            case = self._ensure_challan_draft(session, sighting, actor) if sighting else None
            if case is None:
                raise ValueError("At least four confirmed, dated violations are required")
            return self._challan_detail(session, case)

    def _challan_snapshot(self, session, case):
        sighting = session.get(Sighting, case.sighting_id)
        vehicle = session.get(Vehicle, case.vehicle_id)
        history = self._challan_history(session, sighting)
        ids = [row.id for row in history]
        recognition_ids = select(Detection.recognition_id).join(Sighting, Sighting.detection_id == Detection.id).where(Sighting.id.in_(ids))
        evidence = list(session.scalars(select(Evidence).where(or_(Evidence.sighting_id.in_(ids),
            and_(Evidence.sighting_id.is_(None), Evidence.recognition_id.in_(recognition_ids)))).order_by(Evidence.id)))
        return {"image_policy": "plate_crop", "plate_number": vehicle.plate_number, "vehicle_id": vehicle.vehicle_id,
            "database_vehicle_id": vehicle.id, "department": sighting.payload.get("department", ""),
            "officer_name": vehicle.officer_name, "officer_phone": vehicle.officer_phone,
            "officer_email": vehicle.officer_email, "charged_sighting_id": sighting.id,
            "total_violations": len(history), "fine_amount": case.fine_amount, "challan_id": case.reference,
            "stage_type": "challan", "violations_history": [deepcopy(row.payload) | {"id": row.id, "status": row.status} for row in history],
            "evidence": [{"id": row.id, "evidence_id": row.record_key, "sighting_id": row.sighting_id,
                "recognition_id": row.recognition_id, "full_image": row.full_image,
                "full_image_sha256": row.full_image_sha256, "review_status": row.review_status,
                "plate_crop": row.payload.get("plate_crop", ""),
                "plate_crop_sha256": row.payload.get("plate_crop_sha256", "")} for row in evidence]}

    def _check_challan_evidence(self, session, case, snapshot):
        if snapshot["total_violations"] < 4:
            raise ValueError("The charged observation no longer has four confirmed violations")
        sighting = session.get(Sighting, case.sighting_id)
        detection = session.get(Detection, sighting.detection_id) if sighting.detection_id else None
        linked = [e for e in snapshot["evidence"] if e["sighting_id"] == sighting.id or (
            e["sighting_id"] is None and detection and e["recognition_id"] == detection.recognition_id)]
        if not linked or not any(e["review_status"] == "VERIFIED" for e in linked):
            raise ValueError("The charged observation needs verified evidence before approval or issuance")
        for evidence in snapshot["evidence"]:
            for path_key, hash_key in (("full_image", "full_image_sha256"), ("plate_crop", "plate_crop_sha256")):
                if path_key == "plate_crop" and not evidence[path_key]:
                    continue
                root = settings.snapshots_dir.resolve()
                path = (root / evidence[path_key]).resolve()
                if root not in path.parents or not path.is_file():
                    raise ValueError("A linked evidence file is missing or outside the archive")
                if hashlib.sha256(path.read_bytes()).hexdigest() != evidence[hash_key]:
                    raise ValueError("A linked evidence file failed its integrity check")

    def _challan_detail(self, session, case, include_history=True):
        result = {"id": case.id, "reference": case.reference, "vehicle_id": case.vehicle_id,
            "sighting_id": case.sighting_id, "status": case.status, "version": case.version,
            "fine_amount": case.fine_amount, "created_by": case.created_by, "prepared_by": case.prepared_by, "created_at": iso(case.created_at),
            "approved_by": case.approved_by, "approved_at": iso(case.approved_at),
            "issued_by": case.issued_by, "issued_at": iso(case.issued_at), "due_at": iso(case.due_at),
            "document_sha256": case.document_sha256, "snapshot": deepcopy(case.snapshot)}
        if include_history:
            current = self._challan_snapshot(session, case)
            result["review_snapshot"] = current
            result["review_fingerprint"] = fingerprint(current)
            result["changed_since_approval"] = bool(case.fingerprint and case.fingerprint != fingerprint(current))
            result["history"] = [{"id": event.id, "at": iso(event.occurred_at), "actor": event.actor,
                "action": event.action, "details": event.details} for event in session.scalars(select(ChallanEvent)
                .where(ChallanEvent.challan_id == case.id).order_by(ChallanEvent.id))]
        return result

    def challan_detail(self, case_id):
        with self._lock as session:
            case = session.get(Challan, case_id)
            return self._challan_detail(session, case) if case else None

    def list_challans(self, status=None, vehicle_id=None, limit=30, offset=0):
        with self._lock as session:
            query = select(Challan)
            if status:
                query = query.where(Challan.status == status)
            if vehicle_id is not None:
                query = query.where(Challan.vehicle_id == vehicle_id)
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            return {"total": total, "items": [self._challan_detail(session, case, False) for case in
                session.scalars(query.order_by(Challan.id.desc()).limit(limit).offset(offset))]}

    def challan_action(self, case_id, body, principal):
        actor, role = principal["sub"], principal["role"]
        permissions = {"approve": {"Administrator", "Supervisory Officer"},
            "reject": {"Administrator", "Supervisory Officer"}, "uphold": {"Administrator", "Supervisory Officer"},
            "cancel": {"Administrator", "Supervisory Officer"}, "reopen": {"Administrator", "Supervisory Officer"},
            "issue": {"Administrator", "Transport Officer", "Supervisory Officer"},
            "appeal": {"Administrator", "Transport Officer", "Supervisory Officer"},
            "amend": {"Administrator", "Transport Officer"}}
        if role not in permissions[body.action]:
            raise PermissionError("Your role cannot perform this challan action")
        with self._lock as session:
            case = session.get(Challan, case_id)
            if case is None:
                raise LookupError("Challan not found")
            if body.expected_version != case.version:
                raise ValueError("Case changed; reload it before taking action")
            transitions = {"approve": ({"DRAFT"}, "APPROVED"), "reject": ({"DRAFT", "APPROVED"}, "REJECTED"),
                "issue": ({"APPROVED"}, "ISSUED"), "appeal": ({"ISSUED"}, "APPEALED"),
                "uphold": ({"APPEALED"}, "UPHELD"), "cancel": ({"ISSUED", "APPEALED", "UPHELD"}, "CANCELLED"),
                "amend": ({"DRAFT"}, "DRAFT"), "reopen": ({"APPROVED", "REJECTED"}, "DRAFT")}
            allowed, target = transitions[body.action]
            if case.status not in allowed:
                raise ValueError(f"Cannot {body.action} a {case.status} case")
            before = case.status
            now = get_local_now()
            if body.action == "reopen":
                case.approved_by = case.approved_at = case.fingerprint = None
                case.snapshot = self._challan_snapshot(session, case)
            if body.action == "amend":
                if body.fine_amount is None:
                    raise ValueError("A fine amount is required for amendment")
                old_fine = case.fine_amount
                case.fine_amount = body.fine_amount
                # An amendment makes its author the preparer for independent approval.
                case.prepared_by = actor
                case.snapshot = self._challan_snapshot(session, case)
            if body.action == "approve":
                if actor == case.prepared_by:
                    raise PermissionError("A different officer must approve the preparer's case")
                current = self._challan_snapshot(session, case)
                if body.review_fingerprint != fingerprint(current):
                    raise ValueError("Evidence or vehicle context changed; reload and review the case")
                self._check_challan_evidence(session, case, current)
                case.snapshot, case.fingerprint = current, fingerprint(current)
                case.approved_by, case.approved_at = actor, now
            if body.action == "issue":
                current = self._challan_snapshot(session, case)
                if fingerprint(current) != case.fingerprint:
                    raise ValueError("Approved case data changed; reopen the draft and review the discrepancy")
                self._check_challan_evidence(session, case, current)
                case.issued_by, case.issued_at, case.due_at = actor, now, now + timedelta(days=7)
                document_data = deepcopy(case.snapshot) | {"issued_at": iso(now), "due_at": iso(case.due_at),
                    "approved_by": case.approved_by, "issued_by": actor}
                case.document = render_issued_challan(document_data)
                case.document_sha256 = hashlib.sha256(case.document).hexdigest()
                for metadata in case.snapshot["evidence"]:
                    evidence = session.get(Evidence, metadata["id"])
                    evidence.case_status = "ATTACHED_TO_CHALLAN"
                    evidence.payload = evidence.payload | {"related_challan_id": case.reference,
                        "case_status": "ATTACHED_TO_CHALLAN"}
            if body.action in {"uphold", "cancel"} and case.status == "APPEALED":
                appeal = session.scalar(select(ChallanEvent).where(ChallanEvent.challan_id == case.id,
                    ChallanEvent.action == "APPEAL").order_by(ChallanEvent.id.desc()).limit(1))
                if actor in {case.approved_by, case.issued_by, appeal.actor if appeal else None}:
                    raise PermissionError("An uninvolved supervisory officer must resolve the appeal")
            case.status, case.version = target, case.version + 1
            details = {"before": before, "after": target, "notes": body.notes, "version": case.version}
            if body.action == "amend":
                details.update(previous_fine=old_fine, fine_amount=case.fine_amount)
            self._challan_log(session, case, actor, body.action.upper(), details)
            return self._challan_detail(session, case)

    def challan_document(self, case_id):
        with self._lock as session:
            case = session.get(Challan, case_id)
            if case is None:
                raise LookupError("Challan not found")
            if not case.document:
                raise ValueError("Only an issued challan has an archived PDF")
            if scoped_department() is not None and case.snapshot.get("image_policy") != "plate_crop":
                raise HTTPException(403, "This historical PDF contains raw camera images; administrator access is required")
            return case.reference, case.document

    def issued_challan_data(self, plate, reference=None):
        with self._lock as session:
            if reference:
                case = session.scalar(select(Challan).where(Challan.reference == reference,
                    Challan.status.in_(["ISSUED", "UPHELD"])))
                if case is None:
                    return None
                vehicle = session.get(Vehicle, case.vehicle_id)
                if normalized(plate) not in {vehicle.normalized_plate, normalized(case.snapshot["plate_number"])}:
                    return None
                return deepcopy(case.snapshot) | {"case_id": case.id, "status": case.status,
                    "issued_at": iso(case.issued_at), "due_at": iso(case.due_at), "approved_by": case.approved_by,
                    "issued_by": case.issued_by}
            vehicle = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == normalized(plate)))
            if vehicle is None:
                return None
            query = select(Challan).where(Challan.vehicle_id == vehicle.id, Challan.status.in_(["ISSUED", "UPHELD"]))
            if reference:
                query = query.where(Challan.reference == reference)
            case = session.scalar(query.order_by(Challan.id.desc()).limit(1))
            if case is None:
                return None
            return deepcopy(case.snapshot) | {"case_id": case.id, "status": case.status,
                "issued_at": iso(case.issued_at), "due_at": iso(case.due_at), "approved_by": case.approved_by,
                "issued_by": case.issued_by}

    def log_challan_delivery(self, reference, actor, channel, outcome):
        with self._lock as session:
            case = session.scalar(select(Challan).where(Challan.reference == reference))
            if case:
                self._challan_log(session, case, actor, "DELIVERY", {"channel": channel, "outcome": outcome})
