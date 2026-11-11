"""Transactional change history and access outcomes; never log credentials/bodies."""
from datetime import date, datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from .access import principal_context
from .config import get_local_now
from .db_models import AuditEvent

# Explicit fields prevent secrets, binary images and bulk personal records entering logs.
FIELDS = {
    "users": ("email", "name", "role", "active", "department_id", "token_version"),
    "vehicles": ("plate_number", "vehicle_id", "department_id", "active", "authorized_areas", "duty_schedule"),
    "departments": ("name", "active"),
    "drivers": ("department_id", "active"),
    "vehicle_assignments": ("vehicle_id", "department_id", "status", "valid_from", "valid_until"),
    "duty_slips": ("assignment_id", "status", "valid_from", "valid_until"),
    "plate_recognitions": ("plate_number", "review_status"),
    "evidence": ("review_status", "case_status", "department_id", "full_image_sha256"),
    "geofences": ("name",),
    "government_sightings": ("status", "department_id", "vehicle_id"),
    "challans": ("status", "version", "department_id", "fine_amount", "approved_by", "issued_by"),
    "risk_tasks": ("status", "assigned_role", "acknowledged_by"),
    "duty_reviews": ("sighting_id", "reviewed_by", "notes"),
    "camera_checkpoints": ("camera_id", "name", "x1", "y1", "x2", "y2", "direction", "active", "revision"),
    "checkpoint_crossings": ("checkpoint_id", "track_id", "direction", "revision"),
    "track_links": ("first_track_id", "second_track_id", "normalized_plate", "confirmed_by"),
    "approved_routes": ("name", "department_id", "vehicle_id", "valid_from", "valid_until", "active", "revision", "approved_by"),
    "movement_alert_reviews": ("alert_key", "route_id", "vehicle_id", "status", "reviewed_by"),
    "vehicle_verifications": ("sighting_id", "vehicle_id", "department_id", "status", "risk_status", "reviewed_by"),
}


def value(item):
    return item.isoformat() if isinstance(item, (datetime, date)) else item


@event.listens_for(Session, "before_flush")
def record_changes(session, flush_context, instances):
    for item in list(session.deleted) + list(session.dirty):
        if isinstance(item, AuditEvent):
            raise ValueError("Audit events cannot be changed or deleted")
    principal = principal_context.get()
    if principal is None:
        return
    for item in list(session.new) + list(session.dirty) + list(session.deleted):
        fields = FIELDS.get(getattr(item, "__tablename__", ""))
        if not fields or (item in session.dirty and not session.is_modified(item)):
            continue
        operation = "CREATE" if item in session.new else "DELETE" if item in session.deleted else "UPDATE"
        changes = {}
        state = inspect(item)
        for field in fields:
            history = state.attrs[field].history
            if operation != "UPDATE" or history.has_changes():
                changes[field] = {"before": value(history.deleted[0]) if history.deleted else None,
                                  "after": value(getattr(item, field))}
        # Record that a payload changed without copying credentials or mixed source data.
        if "payload" in state.attrs and state.attrs.payload.history.has_changes():
            changes["payload_changed"] = True
            history = state.attrs.payload.history
            before = history.deleted[0] if history.deleted else {}
            after = getattr(item, "payload") or {}
            for field in ("reviewer", "review_notes", "reviewed_at", "integrity_status", "plate_number",
                          "department", "risk_context", "related_violation_id", "related_challan_id"):
                if before.get(field) != after.get(field):
                    changes[field] = {"before": before.get(field), "after": after.get(field)}
        if "password_hash" in state.attrs and state.attrs.password_hash.history.has_changes():
            changes["password_changed"] = True
        session.add(AuditEvent(occurred_at=get_local_now(), actor=principal["sub"],
            action=f"{item.__tablename__.upper()}_{operation}",
            entity=str(getattr(item, "record_key", None) or getattr(item, "id", None) or getattr(item, "email", "new")),
            department_id=getattr(item, "department_id", None) or principal.get("department_id"),
            details={"role": principal["role"], "changes": changes}))


def log_access(engine, actor, action, entity, status, department_id=None, **details):
    with Session(engine) as session, session.begin():
        session.add(AuditEvent(occurred_at=get_local_now(), actor=actor, action=action,
            entity=entity[:200], department_id=department_id,
            details={"status": status, **details}))
