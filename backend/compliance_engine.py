"""Explainable prototype compliance decisions and violation risk scoring."""
from __future__ import annotations

from datetime import datetime, time


def _rule(rule_id: str, outcome: str, message: str, criteria: str = "") -> dict[str, str]:
    result = {"rule_id": rule_id, "outcome": outcome, "message": message}
    if criteria:
        result["criteria"] = criteria
    return result


def evaluate_compliance(
    vehicle: dict[str, str] | None,
    camera_area: str,
    observed_at: datetime,
    latitude: float | None = None,
    longitude: float | None = None,
    geofences: list[dict] | None = None,
    route_context: dict | None = None,
    duty_context: dict | None = None,
) -> dict:
    """Evaluate configured area and duty rules without treating bad policy data as guilt."""
    if vehicle is None:
        return {
            "status": "UNREGISTERED",
            "violation_criteria": "",
            "decision_reason": "Plate is not present in the government vehicle registry.",
            "rules": [_rule("GOVERNMENT_REGISTRY", "NOT_APPLICABLE", "No registry match")],
        }

    rules: list[dict[str, str]] = []
    violations: list[str] = []
    needs_review = False

    authorized_areas = {
        area.strip() for area in vehicle.get("authorized_areas", "").split("|") if area.strip()
    }
    if not authorized_areas:
        needs_review = True
        rules.append(_rule("AUTHORIZED_AREA", "REVIEW", "No authorized areas are configured"))
    elif camera_area in authorized_areas:
        rules.append(_rule("AUTHORIZED_AREA", "PASS", f"{camera_area} is authorized"))
    else:
        violations.append("UNAUTHORIZED_AREA")
        rules.append(_rule(
            "AUTHORIZED_AREA", "FAIL", f"{camera_area} is outside the vehicle's authorized areas",
            "UNAUTHORIZED_AREA",
        ))

    schedule = vehicle.get("duty_schedule", "").strip().upper()
    if schedule == "24/7":
        rules.append(_rule("DUTY_HOURS", "PASS", "Vehicle is authorized for 24/7 operation"))
    else:
        try:
            start_text, end_text = schedule.split("-", 1)
            start = datetime.strptime(start_text.strip(), "%H:%M").time()
            end = datetime.strptime(end_text.strip(), "%H:%M").time()
        except (ValueError, TypeError):
            needs_review = True
            rules.append(_rule("DUTY_HOURS", "REVIEW", "Duty schedule is missing or invalid"))
        else:
            observed = observed_at.timetz().replace(tzinfo=None)
            on_duty = start <= observed <= end if start <= end else observed >= start or observed <= end
            if on_duty:
                rules.append(_rule("DUTY_HOURS", "PASS", f"Detection is within {schedule}"))
            else:
                violations.append("OUTSIDE_DUTY_HOURS")
                rules.append(_rule(
                    "DUTY_HOURS", "FAIL", f"Detection is outside {schedule}", "OUTSIDE_DUTY_HOURS",
                ))

    from .geofencing import evaluate_geofence
    zone_result = evaluate_geofence(vehicle, geofences or [], latitude, longitude,
                                    (route_context or {}).get("department_id"), duty_context)
    rules.append(_rule("GPS_GEOFENCE", zone_result["outcome"], zone_result["message"], zone_result.get("criteria", "")))
    if zone_result["outcome"] == "REVIEW":
        needs_review = True
    elif zone_result["outcome"] == "FAIL":
        violations.append(zone_result["criteria"])

    if route_context and route_context["outcome"] != "NOT_APPLICABLE":
        route_outcome = route_context["outcome"]
        rules.append(_rule("APPROVED_ROUTE_DATE", route_outcome, route_context["message"],
                           route_context.get("criteria", "")))
        if route_outcome == "REVIEW":
            needs_review = True
        elif route_outcome == "FAIL":
            violations.append(route_context["criteria"])

    if needs_review:
        status = "REVIEW_REQUIRED"
        reason = "Vehicle policy data needs correction before an enforcement decision."
    elif violations:
        status = "VIOLATION"
        reason = "; ".join(rule["message"] for rule in rules if rule["outcome"] == "FAIL")
    else:
        status = "LAWFUL"
        reason = "All configured compliance rules passed."

    return {
        "status": status,
        "violation_criteria": "|".join(violations),
        "decision_reason": reason,
        "rules": rules,
    }


def assess_violation_risk(compliance: dict, prior_violation_count: int = 0) -> dict:
    """Pure default-policy helper. Runtime storage supplies the versioned policy/history."""
    from .risk_engine import RiskPolicyConfig, score_risk
    return score_risk(compliance, RiskPolicyConfig().model_dump(), prior_count=prior_violation_count)
