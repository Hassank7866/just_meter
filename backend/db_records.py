"""Storage adapter preserving existing API snapshots while enforcing SQL relations."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from .config import LOCAL_TZ, get_local_now
from .db_models import Department, Detection, Evidence, Geofence, Recognition, Sighting, Vehicle, VehicleEvent

TABLES = {
    "approved_vehicles_path": (Vehicle, "plate_number"),
    "vehicle_events_path": (VehicleEvent, "event_id"),
    "plate_recognition_path": (Recognition, "recognition_id"),
    "csv_path": (Detection, "_record_key"),
    "government_sightings_path": (Sighting, "_record_key"),
    "evidence_path": (Evidence, "evidence_id"),
    "geofences": (Geofence, "zone_id"),
}


def normalized(value):
    return "".join(c for c in str(value).upper() if c.isalnum())


def timestamp(value):
    if not value:
        return None
    result = datetime.fromisoformat(str(value))
    return result if result.tzinfo else result.replace(tzinfo=LOCAL_TZ)


class Records:
    def _rows(self, name):
        model, _ = TABLES[name]
        with self._lock as session:
            query = select(model).order_by(model.id)
            if model is Vehicle:
                query = query.where(Vehicle.active.is_(True))
            return [deepcopy(item.payload) for item in session.scalars(query)]

    def _lookup(self, session, model, key):
        if not key:
            return None
        return session.scalar(select(model.id).where(model.record_key == key))

    def _append(self, name, row):
        with self._lock as session:
            return self._upsert(session, name, row)

    def _upsert(self, session, name, row):
        model, key_field = TABLES[name]
        row = deepcopy(row)
        key = normalized(row.get(key_field, "")) if model is Vehicle else row.get(key_field)
        key = key or uuid4().hex
        if key_field == "_record_key":
            row[key_field] = key
        item = session.scalar(select(model).where(model.record_key == key))
        if item is None:
            item = model(record_key=key)
            session.add(item)
        previous_department = (item.payload or {}).get("department", "")
        # Match the existing CSV-backed API types, retaining nested new metadata.
        item.payload = {k: ("" if v is None else str(v) if isinstance(v, (int, float, bool)) else v)
                        for k, v in row.items()}
        with session.no_autoflush:
            if model is Vehicle:
                dept_name = row.get("department", "").strip()
                dept = session.scalar(select(Department).where(Department.name == dept_name)) if dept_name else None
                if dept_name and dept is None:
                    dept = Department(name=dept_name)
                    session.add(dept)
                    session.flush([dept])
                item.department_id = dept.id if dept else None
                item.normalized_plate = key
                item.plate_number = row["plate_number"]
                item.vehicle_id = row.get("vehicle_id", "")
                for field in ("officer_name", "officer_email", "officer_phone", "duty_schedule"):
                    setattr(item, field, row.get(field, ""))
                item.authorized_areas = [a.strip() for a in row.get("authorized_areas", "").split("|") if a.strip()]
                item.active = True
            elif model is VehicleEvent:
                item.observed_at = timestamp(row.get("timestamp"))
                item.camera_id = row.get("camera_id", "")
                item.vehicle_count = int(row.get("vehicle_count") or 0)
            elif model is Recognition:
                item.event_id = self._lookup(session, VehicleEvent, row.get("detection_event_id"))
                item.observed_at = timestamp(row.get("timestamp"))
                item.plate_number = row.get("final_text") or row.get("normalized_text", "")
                item.confidence = float(row.get("confidence") or 0)
                item.review_status = row.get("review_status", "REVIEW_REQUIRED")
            elif model is Detection:
                item.recognition_id = self._lookup(session, Recognition, row.get("recognition_id"))
                item.observed_at = timestamp(row.get("timestamp"))
                item.normalized_plate = normalized(row.get("plate_number", ""))
            elif model is Sighting:
                if item.department_id is None:
                    item.department_id = session.scalar(select(Department.id).where(
                        Department.name == str(row.get("department") or "").strip()))
                item.vehicle_id = self._lookup(session, Vehicle, normalized(row.get("plate_number", "")))
                item.detection_id = self._lookup(session, Detection, row.get("detection_key"))
                item.observed_at = timestamp(row.get("timestamp"))
                item.normalized_plate = normalized(row.get("plate_number", ""))
                item.status = row.get("status", "UNASSESSED")
                item.violation_id = row.get("violation_id") or None
            elif model is Evidence:
                if item.department_id is None or previous_department != row.get("department", ""):
                    item.department_id = session.scalar(select(Department.id).where(
                        Department.name == str(row.get("department") or "").strip()))
                item.event_id = self._lookup(session, VehicleEvent, row.get("detection_event_id"))
                item.recognition_id = self._lookup(session, Recognition, row.get("recognition_id"))
                violation = row.get("related_violation_id")
                item.sighting_id = session.scalar(select(Sighting.id).where(Sighting.violation_id == violation)) if violation else None
                old = row.get("status", "")
                item.review_status = row.get("review_status") or (old if old in {"CAPTURED", "UNDER_REVIEW", "VERIFIED"} else "CAPTURED")
                item.case_status = row.get("case_status") or ("ATTACHED_TO_CHALLAN" if row.get("related_challan_id") or old == "ATTACHED_TO_CHALLAN" else "ATTACHED_TO_VIOLATION" if violation or old == "ATTACHED_TO_VIOLATION" else "UNASSIGNED")
                item.payload = item.payload | {"review_status": item.review_status, "case_status": item.case_status}
                item.full_image = row.get("full_image", "")
                item.full_image_sha256 = row.get("full_image_sha256", "")
            elif model is Geofence:
                item.name = row.get("name", "")
        session.flush()
        return item

    def _replace(self, name, rows):
        model, _ = TABLES[name]
        with self._lock as session:
            kept = {self._upsert(session, name, row).id for row in rows}
            for item in session.scalars(select(model)):
                if item.id not in kept:
                    if model is Vehicle:
                        item.active = False  # Historical foreign keys survive registry removal.
                    else:
                        session.delete(item)

    def get_geofences(self):
        return self._rows("geofences")

    def save_geofences(self, zones):
        self._replace("geofences", zones)
