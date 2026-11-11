"""Validated approval windows and conservative route applicability rules."""
from __future__ import annotations

import math
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .config import LOCAL_TZ
from .duty_verification import moment


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=3, max_length=200)
    department_id: int = Field(ge=1)
    vehicle_id: int | None = Field(default=None, ge=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    weekdays: list[int] = Field(default_factory=lambda: list(range(7)), max_length=7)
    camera_ids: list[str] = Field(default_factory=list, max_length=30)
    camera_areas: list[str] = Field(default_factory=list, max_length=30)
    corridor_polygon: list[dict] = Field(default_factory=list, max_length=100)
    require_assignment: bool = False
    require_duty: bool = False
    enforce_dates: bool = False
    active: bool = True

    @model_validator(mode="after")
    def validate_route(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("Route end must follow its start")
        if not self.weekdays or len(set(self.weekdays)) != len(self.weekdays) or any(day not in range(7) for day in self.weekdays):
            raise ValueError("Weekdays must be distinct values from 0 (Monday) to 6 (Sunday)")
        for field in ("camera_ids", "camera_areas"):
            values = [item.strip() for item in getattr(self, field)]
            if any(not item or len(item) > 100 for item in values) or len(set(values)) != len(values):
                raise ValueError(f"{field} must contain distinct nonempty values of at most 100 characters")
            setattr(self, field, values)
        if not (self.camera_ids or self.camera_areas or self.corridor_polygon):
            raise ValueError("An approved route needs a camera, area or corridor")
        if self.corridor_polygon:
            if len(self.corridor_polygon) < 3:
                raise ValueError("A route corridor needs at least three vertices")
            points = []
            for point in self.corridor_polygon:
                try:
                    lat, lon = float(point["latitude"]), float(point["longitude"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError("Corridor vertices need numeric latitude and longitude") from None
                if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError("Corridor coordinate is out of range")
                points.append({"latitude": lat, "longitude": lon})
            if len({(p["latitude"], p["longitude"]) for p in points}) < 3:
                raise ValueError("A route corridor needs three distinct vertices")
            self.corridor_polygon = points
        if self.require_duty:
            self.require_assignment = True
        return self


def route_window(routes: list[dict], observed_at: datetime, duty: dict | None = None) -> dict:
    """Return approval state; conflicting and incomplete context never proves a violation."""
    when = moment(observed_at)
    routes = [route for route in routes if route["active"] and moment(route["approved_at"]) <= when]
    if not routes:
        return {"outcome": "NOT_APPLICABLE", "message": "No approved route policy is configured", "route": None}
    local_day = when.astimezone(LOCAL_TZ).weekday()
    active = [route for route in routes if moment(route["valid_from"]) <= when < moment(route["valid_until"])
              and local_day in route["weekdays"]]
    if not active:
        enforce = any(route["enforce_dates"] for route in routes)
        return {"outcome": "FAIL" if enforce else "REVIEW",
                "message": "Observation is outside the approved route dates" if enforce else "No route approval covers this time",
                "criteria": "OUTSIDE_APPROVED_DATE" if enforce else "", "route": None}
    specific = [route for route in active if route["vehicle_id"] is not None]
    candidates = specific or active
    if len(candidates) != 1:
        return {"outcome": "REVIEW", "message": "Multiple approved routes cover this observation", "route": None}
    route = candidates[0]
    rules = (duty or {}).get("rules") or []
    assignment_pass = any(item["rule_id"] == "DUTY_ASSIGNMENT" and item["outcome"] == "PASS" for item in rules)
    period_pass = any(item["rule_id"] == "DUTY_PERIOD" and item["outcome"] == "PASS" for item in rules)
    if route["require_assignment"] and not assignment_pass:
        return {"outcome": "REVIEW", "message": "Approved route needs a verified active assignment", "route": None}
    if route["require_duty"] and not period_pass:
        return {"outcome": "REVIEW", "message": "Approved route needs an active approved duty slip", "route": None}
    return {"outcome": "PASS", "message": f"Approved route {route['name']} covers this observation time",
            "route": route}
