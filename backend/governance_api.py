"""Account administration, scoped reports and append-only audit retrieval."""
import calendar
import csv
import io
from datetime import date, datetime, time, timedelta
from typing import Literal
from xml.sax.saxutils import escape

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .access import public_user
from .auth import require_principal, require_roles
from .config import LOCAL_TZ, get_local_now
from .db_models import AuditEvent, Challan, Department, Sighting, User


class AccountBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=1, max_length=200)
    role: Literal["Administrator", "Transport Officer", "Supervisory Officer", "Auditor"]
    department_id: int | None = Field(None, gt=0)
    active: bool = True
    password: str | None = Field(None, min_length=10, max_length=72)

    @field_validator("email")
    @classmethod
    def email_address(cls, value):
        if value.count("@") != 1 or not all(value.split("@")) or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address")
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value):
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Password must contain at most 72 UTF-8 bytes")
        return value


def period_bounds(period, anchor):
    anchor = anchor or get_local_now().date()
    if period == "daily":
        return anchor, anchor
    if period == "weekly":
        start = anchor - timedelta(days=anchor.weekday())
        return start, start + timedelta(days=6)
    return anchor.replace(day=1), anchor.replace(day=calendar.monthrange(anchor.year, anchor.month)[1])


def safe_csv(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def create_governance_router(get_store):
    router = APIRouter(prefix="/api", tags=["Accounts, reports and audit"])
    admin = require_roles("Administrator")

    @router.get("/auth/me")
    def me(principal=Depends(require_principal)):
        with get_store()._lock as session:
            user = session.get(User, principal["user_id"])
            dept = session.get(Department, user.department_id) if user.department_id else None
            return public_user(user, dept.name if dept else None)

    @router.post("/auth/logout")
    def logout(principal=Depends(require_principal)):
        with get_store()._lock as session:
            session.get(User, principal["user_id"]).token_version += 1
        return {"success": True}

    @router.get("/users", dependencies=[Depends(admin)])
    def users():
        with get_store()._lock as session:
            return [public_user(user, name) for user, name in session.execute(
                select(User, Department.name).outerjoin(Department).order_by(User.email))]

    @router.get("/departments", dependencies=[Depends(require_principal)])
    def departments():
        with get_store()._lock as session:
            return [{"id": row.id, "name": row.name} for row in session.scalars(
                select(Department).where(Department.active.is_(True)).order_by(Department.name))]

    def save_account(body, identifier, principal):
        store = get_store()
        with store._lock as session:
            user = session.get(User, identifier) if identifier else None
            if identifier and user is None:
                raise HTTPException(404, "User not found")
            if body.role in {"Transport Officer", "Supervisory Officer"} and body.department_id is None:
                raise HTTPException(422, "Assign a department to this officer")
            if body.role in {"Administrator", "Auditor"} and body.department_id is not None:
                raise HTTPException(422, "Administrators and auditors have platform-wide oversight")
            if body.department_id:
                dept = session.get(Department, body.department_id)
                if dept is None or not dept.active:
                    raise HTTPException(422, "Choose an active department")
            duplicate = session.scalar(select(User.id).where(User.email == body.email))
            if duplicate is not None and duplicate != identifier:
                raise HTTPException(409, "This email is already registered")
            if user and user.email != body.email:
                raise HTTPException(422, "Account email is fixed to preserve audit identity")
            if user and user.id == principal["user_id"] and (not body.active or body.role != "Administrator"):
                raise HTTPException(409, "Use another administrator to change your own access")
            if user is None:
                if body.password is None:
                    raise HTTPException(422, "A password is required for a new account")
                user = User(email=body.email, token_version=0)
                session.add(user)
            else:
                user.token_version += 1
            user.name, user.role, user.active, user.department_id = body.name, body.role, body.active, body.department_id
            if body.password is not None:
                user.password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode("ascii")
            session.flush()
            return public_user(user)

    @router.post("/users", status_code=201)
    def create(body: AccountBody, principal=Depends(admin)):
        return save_account(body, None, principal)

    @router.put("/users/{user_id}")
    def update(user_id: int, body: AccountBody, principal=Depends(admin)):
        return save_account(body, user_id, principal)

    @router.post("/users/{user_id}/revoke")
    def revoke(user_id: int, principal=Depends(admin)):
        with get_store()._lock as session:
            user = session.get(User, user_id)
            if user is None:
                raise HTTPException(404, "User not found")
            user.token_version += 1
        return {"success": True}

    @router.get("/audit", dependencies=[Depends(require_roles("Administrator", "Auditor", "Supervisory Officer"))])
    def audit(start_date: date | None = None, end_date: date | None = None,
              actor: str = Query("", max_length=254), action: str = Query("", max_length=100),
              limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        if start_date and end_date and start_date > end_date:
            raise HTTPException(422, "Start date must precede end date")
        query = select(AuditEvent)
        if start_date:
            query = query.where(AuditEvent.occurred_at >= datetime.combine(start_date, time.min, LOCAL_TZ))
        if end_date:
            if end_date == date.max:
                raise HTTPException(422, "Invalid end date")
            query = query.where(AuditEvent.occurred_at < datetime.combine(end_date + timedelta(days=1), time.min, LOCAL_TZ))
        if actor:
            query = query.where(AuditEvent.actor == actor)
        if action:
            query = query.where(AuditEvent.action == action)
        with get_store()._lock as session:
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            return {"total": total, "items": [{"id": row.id, "at": row.occurred_at.isoformat(),
                "actor": row.actor, "action": row.action, "entity": row.entity,
                "department_id": row.department_id, "details": row.details} for row in session.scalars(
                    query.order_by(AuditEvent.id.desc()).limit(limit).offset(offset))]}

    @router.get("/reports/compliance", dependencies=[Depends(require_principal)])
    def report(period: Literal["daily", "weekly", "monthly"] = "monthly", anchor: date | None = None,
               department: str = Query("", max_length=200), format: Literal["json", "csv", "pdf"] = "json"):
        try:
            start, end = period_bounds(period, anchor)
            data = get_store().get_executive_dashboard(start, end, department)
        except (ValueError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        start_at = datetime.combine(start, time.min, LOCAL_TZ)
        end_at = datetime.combine(end + timedelta(days=1), time.min, LOCAL_TZ)
        with get_store()._lock as session:
            query = select(Challan).where(Challan.issued_at >= start_at, Challan.issued_at < end_at)
            if department:
                query = query.join(Sighting).where(Sighting.payload["department"].as_string() == department)
            cases = list(session.scalars(query))
        data["summary"].update(challans_issued=len(cases), cancelled_issued_challans=sum(c.status == "CANCELLED" for c in cases),
                               issued_face_value=sum(c.fine_amount for c in cases))
        data["period"] = period
        data["notes"] = "Issuance counts use issuance time; cancelled cases remain in issuance history. Face value is not collected revenue."
        for row in data["departments"]:
            row["compliance_rate"] = round(100 * row["lawful"] / row["sightings"], 1) if row["sightings"] else None
        ranked = sorted(data["departments"], key=lambda row: (row["compliance_rate"] is None, -(row["compliance_rate"] or 0), row["department"]))
        data["departments"] = [dict(row, rank=index + 1 if row["sightings"] else None) for index, row in enumerate(ranked)]
        if format == "json":
            return data
        filename = f"compliance-{period}-{start.isoformat()}.{format}"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "private, no-store"}
        if format == "csv":
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(["section", "department_or_date", "metric", "value"])
            for key in ("start_date", "end_date", "timezone", "generated_at", "department", "notes"):
                writer.writerow(["metadata", "", key, safe_csv(data[key])])
            for key, value in data["summary"].items():
                writer.writerow(["summary", "", key, value])
            for key, value in data["risk_distribution"].items():
                writer.writerow(["risk", "", key, value])
            for group, label in (("departments", "department"), ("daily", "date")):
                for row in data[group]:
                    for key, value in row.items():
                        if key != label:
                            writer.writerow([group, safe_csv(row[label]), key, safe_csv(value)])
            return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
        output = io.BytesIO()
        styles = getSampleStyleSheet()
        story = [Paragraph("Government Fleet Compliance Report", styles["Title"]),
                 Paragraph(escape(f"{start} to {end} | {department or 'All accessible departments'}"), styles["Normal"]), Spacer(1, 12)]
        def add_table(rows):
            table = Table([[Paragraph(escape(str(cell)), styles["Normal"]) for cell in row] for row in rows], repeatRows=1)
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                      ("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.extend([table, Spacer(1, 12)])
        add_table([["Metric", "Value"]] + [[key.replace("_", " "), value] for key, value in data["summary"].items()])
        add_table([["Department", "Sightings", "Violations", "Lawful %", "Rank"]] + [
            [row["department"], row["sightings"], row["violations"], row["compliance_rate"] if row["compliance_rate"] is not None else "N/A", row["rank"] or "N/A"] for row in data["departments"]])
        add_table([["Risk level", "Observations"]] + list(map(list, data["risk_distribution"].items())))
        add_table([["Date", "Detections", "Violations", "High risk"]] + [[row["date"], row["detections"], row["violations"], row["high_risk"]] for row in data["daily"]])
        story.append(Paragraph(escape(data["notes"]), styles["Normal"]))
        SimpleDocTemplate(output).build(story)
        return Response(output.getvalue(), media_type="application/pdf", headers=headers)

    return router
