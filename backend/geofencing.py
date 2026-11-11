"""Small, auditable polygon geofence helpers for the compliance prototype."""
from __future__ import annotations

import math


def validate_geofence(zone: dict) -> dict:
    name = str(zone.get("name", "")).strip()
    area = str(zone.get("camera_area", "")).strip()
    points = zone.get("polygon")
    if not name or not area:
        raise ValueError("Zone name and camera area are required")
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("A geofence polygon needs at least three vertices")
    normalized = []
    for point in points:
        try:
            lat, lon = float(point["latitude"]), float(point["longitude"])
        except (KeyError, TypeError, ValueError):
            raise ValueError("Each vertex must contain numeric latitude and longitude") from None
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("Vertex coordinates are outside valid latitude/longitude ranges")
        normalized.append({"latitude": lat, "longitude": lon})
    if len({(p["latitude"], p["longitude"]) for p in normalized}) < 3:
        raise ValueError("A geofence polygon needs at least three distinct vertices")
    plates = zone.get("authorized_plates", [])
    if isinstance(plates, str):
        plates = [item.strip().upper() for item in plates.split(",") if item.strip()]
    if not isinstance(plates, list):
        raise ValueError("authorized_plates must be a list")
    kind = str(zone.get("kind", "AUTHORIZED")).upper()
    if kind not in {"AUTHORIZED", "RESTRICTED"}:
        raise ValueError("Geofence kind must be AUTHORIZED or RESTRICTED")
    department_id = zone.get("department_id")
    if department_id in ("", None):
        department_id = None
    elif isinstance(department_id, bool) or not str(department_id).isdigit() or int(department_id) <= 0:
        raise ValueError("Department ID must be a positive integer")
    else:
        department_id = int(department_id)
    return {"name": name, "camera_area": area,
            "authorized_plates": [str(p).strip().upper() for p in plates if str(p).strip()],
            "polygon": normalized, "kind": kind, "department_id": department_id,
            "require_assignment": bool(zone.get("require_assignment", False)),
            "require_duty": bool(zone.get("require_duty", False))}


def point_in_polygon(latitude: float, longitude: float, polygon: list[dict]) -> bool:
    """Ray cast using longitude as x; points on a polygon edge count as inside."""
    x, y = longitude, latitude
    vertices = [(float(p["longitude"]), float(p["latitude"])) for p in polygon]
    inside = False
    for index, (x1, y1) in enumerate(vertices):
        x2, y2 = vertices[(index + 1) % len(vertices)]
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-10 and min(x1, x2) - 1e-10 <= x <= max(x1, x2) + 1e-10 and min(y1, y2) - 1e-10 <= y <= max(y1, y2) + 1e-10:
            return True
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
    return inside


def evaluate_geofence(vehicle: dict, zones: list[dict], latitude: float | None, longitude: float | None,
                      department_id: int | None = None, duty: dict | None = None) -> dict:
    zones = [zone for zone in zones if zone.get("kind", "AUTHORIZED") == "AUTHORIZED"]
    if not zones:
        return {"outcome": "NOT_APPLICABLE", "message": "No geofence zones configured; polygon enforcement is inactive"}
    areas = {item.strip() for item in vehicle.get("authorized_areas", "").split("|") if item.strip()}
    plate = "".join(char for char in vehicle.get("plate_number", "").upper() if char.isalnum())
    applicable = [z for z in zones if z.get("camera_area") in areas and (not z.get("authorized_plates") or plate in {''.join(c for c in str(p).upper() if c.isalnum()) for p in z["authorized_plates"]})]
    if not applicable:
        return {"outcome": "REVIEW", "message": "No geofence is configured for this vehicle's authorized areas"}
    rules = (duty or {}).get("rules") or []
    assignment_pass = any(item["rule_id"] == "DUTY_ASSIGNMENT" and item["outcome"] == "PASS" for item in rules)
    duty_pass = any(item["rule_id"] == "DUTY_PERIOD" and item["outcome"] == "PASS" for item in rules)
    eligible = [zone for zone in applicable if
                (zone.get("department_id") is None or zone["department_id"] == department_id) and
                (not zone.get("require_assignment") or assignment_pass) and
                (not zone.get("require_duty") or duty_pass)]
    if not eligible:
        return {"outcome": "REVIEW", "message": "Geofence coverage requires matching department, assignment or duty context"}
    if latitude is None or longitude is None:
        return {"outcome": "REVIEW", "message": "GPS coordinates are missing; polygon compliance cannot be decided"}
    if any(point_in_polygon(latitude, longitude, zone["polygon"]) for zone in eligible):
        return {"outcome": "PASS", "message": "GPS location is inside an applicable authorized geofence"}
    return {"outcome": "FAIL", "message": "GPS location is outside all applicable authorized geofences", "criteria": "OUTSIDE_GEOFENCE"}
