"""Conservative vehicle attribute comparisons and audited officer review."""
from __future__ import annotations

from sqlalchemy import select

from .config import get_local_now
from .db_models import AuditEvent, Sighting, Vehicle, VehicleVerification, VimsSource
from .duty_verification import moment

FIELDS = ("vehicle_type", "make", "model", "color")
TYPE_GROUPS = {
    "car": "car", "automobile": "car", "sedan": "car",
    "bus": "bus", "truck": "truck", "motorcycle": "motorcycle", "motorbike": "motorcycle",
}


def compare_attributes(expected: dict, observed: dict) -> dict:
    results = {}
    for field in FIELDS:
        left = str(expected.get(field) or "").strip().casefold()
        right = str(observed.get(field) or "").strip().casefold()
        if field == "vehicle_type":
            left, right = TYPE_GROUPS.get(left, ""), TYPE_GROUPS.get(right, "")
        results[field] = "UNKNOWN" if not left or not right else "MATCH" if left == right else "MISMATCH"
    return results


def serialize(item: VehicleVerification) -> dict:
    return {"id": item.id, "sighting_id": item.sighting_id, "vehicle_id": item.vehicle_id,
            "observed_at": item.observed_at.isoformat(), "expected": item.expected,
            "observed": item.observed, "comparisons": item.comparisons,
            "status": item.status, "risk_status": item.risk_status,
            "reviewed_by": item.reviewed_by, "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            "review_notes": item.review_notes}


class VehicleVerificationStore:
    def _capture_verification(self, session, sighting: Sighting, detected_type: str) -> None:
        vehicle = session.get(Vehicle, sighting.vehicle_id) if sighting.vehicle_id else None
        if vehicle is None:
            return
        source = session.get(VimsSource, vehicle.vims_source_id) if vehicle.vims_source_id else None
        when = sighting.observed_at
        # A later source revision cannot assert what the registry said at capture time.
        trusted = bool(source and source.exported_at and when and
                       moment(source.exported_at) <= moment(when))
        expected = {field: str((vehicle.vims_payload or {}).get(field) or "").strip()
                    for field in FIELDS} if trusted else {}
        observed = {"vehicle_type": str(detected_type or "").strip(), "make": "", "model": "", "color": ""}
        comparisons = compare_attributes(expected, observed)
        status = "REVIEW_REQUIRED" if "MISMATCH" in comparisons.values() else \
                 "CONSISTENT" if "MATCH" in comparisons.values() else "INSUFFICIENT_DATA"
        session.add(VehicleVerification(sighting_id=sighting.id, vehicle_id=vehicle.id,
            department_id=sighting.department_id, observed_at=when, expected=expected,
            observed=observed, comparisons=comparisons, status=status, risk_status="NONE",
            review_notes=""))

    def list_vehicle_verifications(self, vehicle_id: int, limit: int = 100) -> list[dict] | None:
        with self._lock as session:
            if session.get(Vehicle, vehicle_id) is None:
                return None
            rows = session.scalars(select(VehicleVerification).where(
                VehicleVerification.vehicle_id == vehicle_id).order_by(
                VehicleVerification.observed_at.desc(), VehicleVerification.id.desc()).limit(limit))
            return [serialize(row) for row in rows]

    def vehicle_verification_risk_queue(self, limit: int = 100) -> list[dict]:
        with self._lock as session:
            rows = session.scalars(select(VehicleVerification).where(
                VehicleVerification.risk_status == "HIGH_REVIEW").order_by(
                VehicleVerification.reviewed_at.desc(), VehicleVerification.id.desc()).limit(limit))
            return [serialize(row) for row in rows]

    def review_vehicle_verification(self, vehicle_id: int, verification_id: int,
                                    observed: dict, decision: str, notes: str, actor: str) -> dict:
        if decision not in {"CONFIRMED_MISMATCH", "DISMISSED"}:
            raise ValueError("Decision must confirm or dismiss a mismatch")
        with self._lock as session:
            item = session.get(VehicleVerification, verification_id)
            if item is None or item.vehicle_id != vehicle_id or session.get(Vehicle, vehicle_id) is None:
                raise LookupError("Verification not found")
            if item.reviewed_at is not None:
                raise ValueError("Verification has already been reviewed")
            merged = {field: (str(observed.get(field) or "").strip() if field != "vehicle_type"
                              else item.observed.get(field, "")) for field in FIELDS}
            comparisons = compare_attributes(item.expected, merged)
            if decision == "CONFIRMED_MISMATCH" and "MISMATCH" not in comparisons.values():
                raise ValueError("No comparable attribute mismatch is present")
            item.observed = merged
            item.comparisons = comparisons
            item.status = decision
            item.risk_status = "HIGH_REVIEW" if decision == "CONFIRMED_MISMATCH" else "NONE"
            item.reviewed_by = actor
            item.reviewed_at = get_local_now()
            item.review_notes = notes.strip()
            session.add(AuditEvent(occurred_at=item.reviewed_at, actor=actor,
                action="VEHICLE_VERIFICATION_REVIEWED", entity=str(item.id),
                department_id=item.department_id,
                details={"sighting_id": item.sighting_id, "decision": decision,
                         "comparisons": comparisons, "risk_status": item.risk_status}))
            session.flush()
            return serialize(item)
