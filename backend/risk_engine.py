"""Versioned, explainable policy scoring. Scores are not probabilities."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RiskPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_weights: dict[str, int] = Field(default_factory=lambda: {
        "UNAUTHORIZED_AREA": 35, "OUTSIDE_GEOFENCE": 40, "OUTSIDE_DUTY_HOURS": 25,
        "UNAUTHORIZED_DATE": 25, "ASSIGNMENT_MISMATCH": 45,
        "NO_VALID_DUTY_SLIP": 40, "UNAUTHORIZED_DESTINATION": 40,
        "VEHICLE_TYPE_MISMATCH": 65, "VEHICLE_APPEARANCE_MISMATCH": 65,
        "PLATE_MISMATCH": 80,
    })
    recurrence_days: int = Field(30, ge=1, le=365)
    repeat_points: int = Field(10, ge=0, le=30)
    repeat_cap: int = Field(30, ge=0, le=50)
    sensitive_assignment_points: int = Field(5, ge=0, le=20)
    critical_assignment_points: int = Field(10, ge=0, le=30)
    severe_history_points: int = Field(5, ge=0, le=20)
    severe_history_cap: int = Field(10, ge=0, le=30)
    medium_threshold: int = Field(25, ge=1, le=97)
    high_threshold: int = Field(50, ge=2, le=98)
    critical_threshold: int = Field(75, ge=3, le=100)
    challan_review_threshold: int = Field(50, ge=1, le=100)

    @model_validator(mode="after")
    def validate_policy(self):
        if not self.medium_threshold < self.high_threshold < self.critical_threshold:
            raise ValueError("Risk thresholds must be strictly increasing")
        required = set(type(self).model_fields["category_weights"].default_factory())
        if set(self.category_weights) != required:
            raise ValueError("Category weights must include exactly the supported violation criteria")
        if any(type(v) is not int or not 0 <= v <= 100 for v in self.category_weights.values()):
            raise ValueError("Category weights must be integers between 0 and 100")
        return self


ROUTE_CRITERIA = {"UNAUTHORIZED_AREA", "OUTSIDE_GEOFENCE", "UNAUTHORIZED_DESTINATION"}
INTEGRITY_CRITERIA = {"VEHICLE_TYPE_MISMATCH", "VEHICLE_APPEARANCE_MISMATCH", "PLATE_MISMATCH"}


def score_risk(compliance: dict, policy: dict, *, prior_count=0, prior_severe_count=0,
               assignment_context="", policy_version=1) -> dict:
    config = RiskPolicyConfig.model_validate(policy)
    result = {
        "risk_score": 0, "risk_level": "NOT_APPLICABLE", "risk_factors": [],
        "risk_breakdown": [], "risk_policy_version": policy_version,
        "risk_window_days": config.recurrence_days, "risk_prior_count": prior_count,
        "risk_context": assignment_context or "UNKNOWN", "risk_missing_context": [],
        "notification_priority": "NONE", "escalation_role": "",
        "recommended_action": "NONE", "requires_officer_approval": True,
    }
    if compliance.get("status") == "REVIEW_REQUIRED":
        return result | {"risk_level": "PENDING_REVIEW"}
    if compliance.get("status") != "VIOLATION":
        return result
    criteria = set(filter(None, compliance.get("violation_criteria", "").split("|")))
    unknown = criteria - config.category_weights.keys()
    if unknown or not criteria:
        return result | {"risk_level": "PENDING_REVIEW", "risk_missing_context": [
            "Unsupported or missing violation criteria: " + ", ".join(sorted(unknown))],
            "notification_priority": "REVIEW", "escalation_role": "Supervisory Officer",
            "recommended_action": "POLICY_REVIEW"}

    contributions = []
    route = criteria & ROUTE_CRITERIA
    if route:
        points = max(config.category_weights[c] for c in route)
        contributions.append({"factor": "Route breach (maximum of overlapping checks)", "points": points,
                              "criteria": sorted(route)})
    for criterion in sorted(criteria - ROUTE_CRITERIA):
        contributions.append({"factor": criterion, "points": config.category_weights[criterion]})
    if prior_count:
        contributions.append({"factor": f"Prior violations in {config.recurrence_days} days ({prior_count})",
                              "points": min(max(0, prior_count) * config.repeat_points, config.repeat_cap)})
    if assignment_context in {"SENSITIVE", "CRITICAL"}:
        contributions.append({"factor": f"Registered assignment context: {assignment_context}",
                              "points": config.sensitive_assignment_points if assignment_context == "SENSITIVE" else config.critical_assignment_points})
    elif assignment_context != "STANDARD":
        result["risk_missing_context"].append("Assignment risk context has not been configured")
    if prior_severe_count:
        contributions.append({"factor": f"Prior High/Critical violations ({prior_severe_count})",
                              "points": min(prior_severe_count * config.severe_history_points, config.severe_history_cap)})
    score = min(100, sum(c["points"] for c in contributions))
    minimum = config.critical_threshold if "PLATE_MISMATCH" in criteria else config.high_threshold if criteria & INTEGRITY_CRITERIA else 0
    if score < minimum:
        contributions.append({"factor": "Confirmed integrity mismatch minimum severity", "points": minimum - score})
        score = minimum
    level = "CRITICAL" if score >= config.critical_threshold else "HIGH" if score >= config.high_threshold else "MEDIUM" if score >= config.medium_threshold else "LOW"
    result.update(risk_score=score, risk_level=level, risk_breakdown=contributions,
                  risk_factors=[f"{c['factor']}: +{c['points']}" for c in contributions],
                  notification_priority={"LOW": "NORMAL", "MEDIUM": "ELEVATED", "HIGH": "HIGH", "CRITICAL": "URGENT"}[level],
                  escalation_role="Supervisory Officer" if level in {"HIGH", "CRITICAL"} else "Transport Officer",
                  recommended_action="CHALLAN_REVIEW" if score >= config.challan_review_threshold else "WARNING_REVIEW")
    return result
