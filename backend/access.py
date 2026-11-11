"""Request-local department restrictions, applied before SQL pagination/aggregation.

Core table subqueries intentionally avoid recursively applying ORM criteria.
Background ingestion and migrations have no principal; HTTP middleware always
sets one. Never reuse a Session across requests or principals.
"""
from contextvars import ContextVar

from fastapi import HTTPException
from sqlalchemy import event, false, or_, select
from sqlalchemy.orm import Session, with_loader_criteria

from . import db_models as m

principal_context = ContextVar("principal", default=None)


def scoped_department():
    principal = principal_context.get()
    if principal is None or principal["role"] in {"Administrator", "Auditor"}:
        return None
    return principal.get("department_id") or -1


@event.listens_for(Session, "do_orm_execute")
def restrict_department(state):
    department = scoped_department()
    if department is None or not state.is_select:
        return
    v, s, e, d, r, a, risk, cases = (model.__table__ for model in (
        m.Vehicle, m.Sighting, m.Evidence, m.Detection, m.Recognition,
        m.VehicleAssignment, m.RiskAssessment, m.Challan))
    vehicles = select(v.c.id).where(v.c.department_id == department)
    sightings = select(s.c.id).where(s.c.department_id == department)
    detections = select(s.c.detection_id).where(s.c.department_id == department)
    recognitions = select(e.c.recognition_id).where(e.c.department_id == department)
    assignments = select(a.c.id).where(a.c.department_id == department)
    assessments = select(risk.c.id).where(risk.c.sighting_id.in_(sightings))
    case_ids = select(cases.c.id).where(cases.c.department_id == department, cases.c.vehicle_id.in_(vehicles))
    criteria = {
        m.Department: m.Department.id == department,
        m.Vehicle: m.Vehicle.department_id == department,
        m.ApprovedRoute: m.ApprovedRoute.department_id == department,
        m.MovementAlertReview: m.MovementAlertReview.vehicle_id.in_(vehicles),
        m.VehicleVerification: m.VehicleVerification.vehicle_id.in_(vehicles),
        m.Driver: m.Driver.department_id == department,
        m.VehicleAssignment: m.VehicleAssignment.department_id == department,
        m.DutySlip: m.DutySlip.assignment_id.in_(assignments),
        m.Sighting: m.Sighting.department_id == department,
        m.Evidence: m.Evidence.department_id == department,
        m.Detection: m.Detection.id.in_(detections),
        m.Recognition: m.Recognition.id.in_(recognitions),
        # Frame boxes/counts can include other departments and unidentified vehicles.
        m.VehicleEvent: false(),
        m.RiskAssessment: m.RiskAssessment.sighting_id.in_(sightings),
        m.RiskTask: m.RiskTask.assessment_id.in_(assessments),
        m.DutyReview: m.DutyReview.sighting_id.in_(sightings),
        m.Challan: m.Challan.id.in_(case_ids),
        m.ChallanEvent: m.ChallanEvent.challan_id.in_(case_ids),
        m.AuditEvent: m.AuditEvent.department_id == department,
        m.User: m.User.id == (principal_context.get() or {}).get("user_id", -1),
    }
    state.statement = state.statement.options(*(
        with_loader_criteria(model, condition, include_aliases=True)
        for model, condition in criteria.items()))


def require_vehicle(store, plate):
    if scoped_department() is not None and store.twin_vehicle_id(plate) is None:
        raise HTTPException(404, "Vehicle not found")


def snapshot_allowed(store, relative):
    """Only department-owned plate crops are safe for scoped officers.

    Full frames may contain other vehicles even if only one plate was recognized.
    Keep raw frames with administrators until image redaction is implemented.
    """
    from pathlib import PurePosixPath
    if not relative or "\\" in relative or ".." in PurePosixPath(relative).parts:
        return False
    if scoped_department() is None:
        return True
    with store._lock as session:
        return session.scalar(select(m.Evidence.id).where(
            m.Evidence.payload["plate_crop"].as_string() == relative)) is not None


def public_user(user, department=None):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "active": user.active, "department_id": user.department_id, "department": department}


def scoped_source_records(session, records, source_id):
    """Hide historical VIMS attributes belonging to another department after transfer."""
    if scoped_department() is None:
        return records
    allowed = set(session.scalars(select(m.Department.vims_external_id).where(m.Department.vims_source_id == source_id)))
    result = {kind: {} for kind in records}
    result["departments"] = {key: row for key, row in records["departments"].items() if key in allowed}
    for kind in ("vehicles", "drivers", "assignments"):
        result[kind] = {key: row for key, row in records[kind].items() if row.get("department_external_id") in allowed}
    result["duty_slips"] = {key: row for key, row in records["duty_slips"].items()
                            if row.get("assignment_external_id") in result["assignments"]}
    return result
