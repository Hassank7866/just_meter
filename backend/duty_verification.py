"""Duty checks over an as-of source snapshot. No inferred trip purpose."""
from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class CoverageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    max_age_hours: int = Field(default=72, ge=1, le=720)

    @model_validator(mode="after")
    def interval(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("Coverage end must follow its start")
        return self


class DutyReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    destination: Literal["MATCH", "MISMATCH", "UNRESOLVED"] = "UNRESOLVED"
    purpose: Literal["MATCH", "MISMATCH", "UNRESOLVED"] = "UNRESOLVED"
    notes: str = Field(min_length=10, max_length=2000)


def moment(value):
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def within(record, when):
    return moment(record["valid_from"]) <= when < moment(record["valid_until"])


def rule(name, outcome, message, criteria=""):
    return {"rule_id": name, "outcome": outcome, "message": message, "criteria": criteria}


def finish(result):
    rules = result["rules"]
    result["status"] = "FAIL" if any(r["outcome"] == "FAIL" for r in rules) else "REVIEW" if any(r["outcome"] == "REVIEW" for r in rules) else "PASS"
    result["review_required"] = any(r["outcome"] == "REVIEW" for r in rules)
    result["reviewable"] = [r["rule_id"] for r in rules if r["outcome"] == "REVIEW" and r["rule_id"] in {"DUTY_DESTINATION", "DUTY_PURPOSE"}]
    return result


def verify_snapshot(snapshot, vehicle_external_id, observed_at, camera_area):
    """A single matching slip is required; areas never prove arrival or purpose."""
    when = moment(observed_at)
    result = {"source": snapshot["source"], "source_revision": snapshot["source_revision"],
              "exported_at": snapshot["exported_at"], "observed_at": when.isoformat(),
              "camera_area": camera_area, "assignment": None, "duty_slip": None, "rules": []}
    rules = result["rules"]
    records = snapshot["records"]
    assignments = [a for a in records["assignments"].values() if a["vehicle_external_id"] == vehicle_external_id
                   and a["status"] == "ACTIVE" and within(a, when)]
    if len(assignments) > 1:
        rules.append(rule("DUTY_ASSIGNMENT", "REVIEW", "Multiple assignments cover this capture; resolve the source conflict"))
        return finish(result)
    if not assignments:
        rules.append(rule("DUTY_ASSIGNMENT", "FAIL", "No active assignment covers the detection time", "ASSIGNMENT_MISMATCH"))
        return finish(result)
    assignment = assignments[0]
    result["assignment"] = deepcopy(assignment)
    vehicle = records["vehicles"].get(vehicle_external_id)
    driver = records["drivers"].get(assignment["driver_external_id"])
    department = records["departments"].get(assignment["department_external_id"])
    if not all((vehicle, driver, department)) or not all(r.get("active", False) for r in (vehicle, driver, department)):
        rules.append(rule("DUTY_ASSIGNMENT", "REVIEW", "Assignment references missing or inactive source records"))
        return finish(result)
    if any(r["department_external_id"] != assignment["department_external_id"] for r in (vehicle, driver)):
        rules.append(rule("DUTY_ASSIGNMENT", "REVIEW", "Assignment department conflicts with the source registry"))
        return finish(result)
    rules.append(rule("DUTY_ASSIGNMENT", "PASS", "An active assignment covers the detection time"))
    slips = [d for d in records["duty_slips"].values() if d["assignment_external_id"] == assignment["external_id"]]
    candidates = [d for d in slips if d["status"] == "ACTIVE" and within(d, when)]
    if len(candidates) > 1:
        rules.append(rule("DUTY_SLIP", "REVIEW", "Multiple active duty slips cover this capture; resolve the source conflict"))
        return finish(result)
    if not candidates:
        reason = "No active duty slip covers the detection time"
        if any(d["status"] == "CANCELLED" and within(d, when) for d in slips):
            reason = "The duty slip for this period was cancelled"
        elif any(d["status"] == "ACTIVE" for d in slips):
            reason = "Detection falls outside the approved duty-slip periods"
        rules.append(rule("DUTY_PERIOD", "FAIL", reason, "NO_VALID_DUTY_SLIP"))
        return finish(result)
    duty = candidates[0]
    result["duty_slip"] = deepcopy(duty)
    if not duty.get("approved_by") or not duty.get("purpose"):
        rules.append(rule("DUTY_APPROVAL", "REVIEW", "Duty approval or purpose is missing from source data"))
        return finish(result)
    rules.append(rule("DUTY_PERIOD", "PASS", "Active approved duty slip covers the detection time"))
    areas = {a.strip().casefold() for a in duty["authorized_areas"]}
    if not camera_area or not areas:
        rules.append(rule("DUTY_AREA", "REVIEW", "An observed area and approved areas are required"))
    elif camera_area.strip().casefold() not in areas:
        rules.append(rule("DUTY_AREA", "FAIL", "Detection is outside the duty slip's authorized areas", "UNAUTHORIZED_DESTINATION"))
    else:
        rules.append(rule("DUTY_AREA", "PASS", "Camera area is authorized by the duty slip"))
    rules.append(rule("DUTY_DESTINATION", "REVIEW", f"Approved destination: {duty['destination']}. Area membership does not establish arrival or route purpose"))
    rules.append(rule("DUTY_PURPOSE", "REVIEW", f"Approved purpose: {duty['purpose']}. Officer evidence is needed to confirm trip context"))
    return finish(result)


def merge_duty(base, duty):
    result = deepcopy(base)
    result["base_compliance"] = deepcopy(base)
    result["duty_verification"] = deepcopy(duty)
    result["rules"] = base.get("rules", []) + duty["rules"]
    criteria = list(filter(None, base.get("violation_criteria", "").split("|")))
    criteria.extend(r["criteria"] for r in duty["rules"] if r["outcome"] == "FAIL" and r.get("criteria"))
    result["violation_criteria"] = "|".join(dict.fromkeys(criteria))
    # An unresolved duty question does not erase an independent confirmed area/hour violation.
    if base["status"] == "VIOLATION" or duty["status"] == "FAIL":
        result["status"] = "VIOLATION"
        result["decision_reason"] = "; ".join(r["message"] for r in result["rules"] if r["outcome"] == "FAIL")
    elif base["status"] == "REVIEW_REQUIRED" or duty["review_required"]:
        result["status"] = "REVIEW_REQUIRED"
        result["decision_reason"] = "; ".join(r["message"] for r in result["rules"] if r["outcome"] == "REVIEW")
    return result
