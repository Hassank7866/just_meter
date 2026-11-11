"""Executive summaries of stored observations, with capture-time attribution."""
from collections import Counter
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import LOCAL_TZ, LOCAL_TIMEZONE, get_local_now
from .db_models import Department, Detection, RiskAssessment, RiskTask, Sighting, Vehicle


def department_name(payload):
    return str(payload.get("department") or "").strip() or "Unassigned"


def identity(sighting):
    return ("vehicle", sighting.vehicle_id) if sighting.vehicle_id else ("plate", sighting.normalized_plate)


def local_day(value):
    # SQLite test dates lose their timezone; persisted naive legacy dates are local.
    return (value if value.tzinfo else value.replace(tzinfo=LOCAL_TZ)).astimezone(LOCAL_TZ).date().isoformat()


class DashboardStore:
    def get_executive_dashboard(self, start_date: date | None = None,
                                end_date: date | None = None, department: str = ""):
        end_date = end_date or get_local_now().date()
        start_date = start_date or end_date - timedelta(days=29)
        days = (end_date - start_date).days + 1
        if not 1 <= days <= 366 or end_date == date.max:
            raise ValueError("Choose an ordered date range of at most 366 days")
        start = datetime.combine(start_date, time.min, LOCAL_TZ)
        end = datetime.combine(end_date + timedelta(days=1), time.min, LOCAL_TZ)
        department = department.strip()
        # Read-only analytics must not acquire the writer's global advisory lock.
        with Session(self.engine) as session:
            if self.engine.dialect.name == "postgresql":
                session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            fleet = list(session.execute(select(Vehicle, Department.name).outerjoin(
                Department, Vehicle.department_id == Department.id).where(Vehicle.active.is_(True))))
            captured_departments = list(session.scalars(select(Sighting.payload["department"].as_string()).distinct()))
            options = sorted({name or "Unassigned" for _, name in fleet} |
                             {str(name or "").strip() or "Unassigned" for name in captured_departments})
            if department and department not in options:
                raise ValueError("Unknown department")
            dept_expr = func.coalesce(func.nullif(func.trim(Sighting.payload["department"].as_string()), ""), "Unassigned")
            conditions = [Sighting.observed_at >= start, Sighting.observed_at < end]
            if department:
                conditions.append(dept_expr == department)
            observations = list(session.execute(select(Sighting, RiskAssessment, RiskTask).outerjoin(
                RiskAssessment, RiskAssessment.sighting_id == Sighting.id).outerjoin(
                RiskTask, RiskTask.assessment_id == RiskAssessment.id).where(*conditions)))
            detection_query = select(Detection.observed_at).where(Detection.observed_at >= start, Detection.observed_at < end)
            if department:
                detection_query = detection_query.join(Sighting, Sighting.detection_id == Detection.id).where(dept_expr == department)
            detection_dates = list(session.scalars(detection_query))

            daily = {(start_date + timedelta(days=i)).isoformat(): {
                "date": (start_date + timedelta(days=i)).isoformat(), "detections": 0,
                "sightings": 0, "violations": 0, "high_risk": 0} for i in range(days)}
            for when in detection_dates:
                daily[local_day(when)]["detections"] += 1
            departments = {}

            def dept_row(name):
                return departments.setdefault(name, {"department": name, "registered_vehicles": 0,
                    "sightings": 0, "violations": 0, "lawful": 0, "review_required": 0,
                    "open_tasks": 0, "identities": set()})

            for vehicle, name in fleet:
                name = name or "Unassigned"
                if not department or department == name:
                    dept_row(name)["registered_vehicles"] += 1
            statuses = Counter()
            levels = {level: 0 for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL", "PENDING_REVIEW", "UNASSESSED")}
            observed, violated = set(), set()
            legacy_risk = 0
            alerts = []
            acknowledged = 0
            for sighting, assessment, task in observations:
                row = dept_row(department_name(sighting.payload))
                row["sightings"] += 1
                row["identities"].add(identity(sighting))
                observed.add(identity(sighting))
                statuses[sighting.status] += 1
                day = daily[local_day(sighting.observed_at)]
                day["sightings"] += 1
                if sighting.status == "VIOLATION":
                    violated.add(identity(sighting))
                    row["violations"] += 1
                    day["violations"] += 1
                    level = assessment.level if assessment else str(sighting.payload.get("risk_level", ""))
                    level = level if level in levels else "UNASSESSED"
                    levels[level] += 1
                    if assessment is None and level != "UNASSESSED":
                        legacy_risk += 1
                    if level in {"HIGH", "CRITICAL"}:
                        day["high_risk"] += 1
                elif sighting.status == "LAWFUL":
                    row["lawful"] += 1
                else:
                    row["review_required"] += 1
                if task and task.status == "ACKNOWLEDGED":
                    acknowledged += 1
                if task and task.status == "OPEN":
                    row["open_tasks"] += 1
                    alerts.append({"id": task.id, "plate_number": sighting.payload.get("plate_number", ""),
                        "department": row["department"], "timestamp": sighting.observed_at.isoformat(),
                        "risk_level": assessment.level, "risk_score": assessment.score,
                        "priority": task.priority, "assigned_role": task.assigned_role,
                        "recommended_action": task.recommended_action, "violation_id": sighting.violation_id})

            # Stage uses all prior violations, even when the view starts after them.
            # Group on durable vehicle identity so a corrected plate does not reset history.
            counts = Counter()
            if violated:
                history = session.execute(select(Sighting.vehicle_id, Sighting.normalized_plate, func.count()).where(
                    Sighting.status == "VIOLATION", Sighting.observed_at < end).group_by(
                    Sighting.vehicle_id, Sighting.normalized_plate))
                for vehicle_id, plate, count in history:
                    key = ("vehicle", vehicle_id) if vehicle_id else ("plate", plate)
                    if key in violated:
                        counts[key] += count
            warnings = sum(0 < count < 4 for count in counts.values())
            challans = sum(count >= 4 for count in counts.values())
            for row in departments.values():
                row["observed_vehicles"] = len(row.pop("identities"))
            alerts.sort(key=lambda item: (-item["risk_score"], -item["id"]))
            return {
                "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
                "timezone": LOCAL_TIMEZONE, "department": department, "department_options": options,
                "generated_at": get_local_now().isoformat(),
                "summary": {"registered_vehicles": sum(row["registered_vehicles"] for row in departments.values()),
                    "detections": len(detection_dates), "sightings": len(observations),
                    "observed_vehicles": len(observed), "violations": statuses["VIOLATION"],
                    "lawful": statuses["LAWFUL"],
                    "review_required": len(observations) - statuses["VIOLATION"] - statuses["LAWFUL"],
                    "open_tasks": len(alerts), "acknowledged_tasks": acknowledged,
                    "warning_stage_vehicles": warnings, "challan_eligible_vehicles": challans},
                "departments": sorted(departments.values(), key=lambda row: (-row["violations"], row["department"])),
                "risk_distribution": levels, "legacy_risk_count": legacy_risk,
                "daily": list(daily.values()), "alerts": alerts[:20],
            }
