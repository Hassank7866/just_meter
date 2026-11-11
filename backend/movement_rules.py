"""Review-only findings from approved routes and trusted movement observations."""
from __future__ import annotations

from hashlib import sha256
import math

from .geofencing import point_in_polygon
from .route_policy import route_window
from .tracking_store import plate_key


def _location(event):
    try:
        lat = float(event["latitude"])
        lon = float(event["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lon) if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180 else None


def movement_findings(events: list[dict], routes: list[dict], zones: list[dict], vehicle: dict,
                      duty_at) -> list[dict]:
    """Never infer identity from raw plate text or generate an enforcement decision."""
    findings = []
    prior_checkpoint = {}
    prior_boundary = {}
    confirmed_pairs = {frozenset((item["from_track_id"], item["to_track_id"]))
                       for item in events if item["kind"] == "confirmed_link"}

    def connected(first, second):
        return first and second and (first == second or frozenset((first, second)) in confirmed_pairs)

    def add(route, kind, event, message, zone_id=""):
        source = f"{route['id']}:{route['revision']}:{kind}:{event['kind']}:{event['id']}:{zone_id}"
        findings.append({"alert_key": sha256(source.encode()).hexdigest()[:40],
            "route_id": route["id"], "route_name": route["name"], "route_revision": route["revision"],
            "kind": kind, "status": "REVIEW_REQUIRED", "message": message,
            "observed_at": event["at"], "camera_id": event.get("camera_id") or "",
            "source_kind": event["kind"], "source_id": event["id"],
            "track_id": event.get("track_id") or "", "zone_id": zone_id})

    for event in sorted(events, key=lambda item: (item["at"] or "", item["id"])):
        if event["kind"] not in {"sighting", "checkpoint_crossing"}:
            continue
        if event["kind"] == "sighting" and event.get("identity_evidence") != "MANUAL_REVIEW":
            continue
        duty = event.get("duty_verification") or duty_at(event)
        context = route_window(routes, event["at"], duty)
        if context["outcome"] != "PASS":
            continue
        route = context["route"]
        track_key = event.get("track_id")
        if event["kind"] == "checkpoint_crossing":
            camera_id = event.get("camera_id") or ""
            ordered = route["camera_ids"]
            if ordered and camera_id not in ordered:
                add(route, "ROUTE_DEVIATION", event, "Reviewed track crossed a checkpoint outside the approved route")
            elif ordered:
                position = ordered.index(camera_id)
                prior = prior_checkpoint.get(route["id"])
                if prior and connected(prior[1], track_key) and position < prior[0]:
                    add(route, "ABNORMAL_SEQUENCE", event, "Connected track reached an earlier checkpoint after a later one")
                prior_checkpoint[route["id"]] = (position, track_key)
            continue

        area = event.get("camera_area") or ""
        camera_id = event.get("camera_id") or ""
        if route["camera_ids"] and camera_id and camera_id not in route["camera_ids"]:
            add(route, "ROUTE_DEVIATION", event, "Reviewed sighting is at a camera outside the approved route")
        elif route["camera_areas"] and area and area not in route["camera_areas"]:
            add(route, "ROUTE_DEVIATION", event, "Reviewed sighting is outside approved route areas")
        location = _location(event)
        if location is None:
            continue
        lat, lon = location
        if route["corridor_polygon"]:
            inside = point_in_polygon(lat, lon, route["corridor_polygon"])
            prior = prior_boundary.get(route["id"])
            if prior and connected(prior[1], track_key) and prior[0] and not inside:
                add(route, "BOUNDARY_CROSSING", event, "Connected observations moved outside the approved corridor")
            elif not inside:
                add(route, "ROUTE_DEVIATION", event, "Reviewed sighting is outside the approved corridor")
            prior_boundary[route["id"]] = (inside, track_key)
        for zone in zones:
            if zone.get("kind") != "RESTRICTED":
                continue
            if zone.get("department_id") not in (None, vehicle["department_id"]):
                continue
            exemptions = {plate_key(item) for item in zone.get("authorized_plates", [])}
            if plate_key(vehicle["plate_number"]) in exemptions:
                continue
            if point_in_polygon(lat, lon, zone["polygon"]):
                add(route, "UNAUTHORIZED_VISIT", event,
                    f"Reviewed sighting falls inside restricted zone {zone['name']}", zone.get("zone_id") or "")
    return findings
