"""Conservative movement trail from linked sightings and reviewed camera tracks."""
from __future__ import annotations

from sqlalchemy import or_, select

from .access import scoped_department
from .config import get_local_now
from .db_models import (ApprovedRoute, AuditEvent, CheckpointCrossing, Detection,
                        Geofence, MovementAlertReview, Recognition, Sighting,
                        TrackLink, Vehicle, VehicleTrack)
from .duty_verification import moment
from .movement_rules import movement_findings
from .route_store import route_dict
from .tracking_store import plate_key


def _at(value):
    return moment(value).isoformat() if value else None


def _reviewed_track(session, recognition):
    read = recognition.get if hasattr(recognition, "get") else lambda key: getattr(recognition, key)
    data = read("payload") or {}
    if read("review_status") != "ACCEPTED" or not data.get("reviewer") or not data.get("track_id"):
        return None
    track = session.scalar(select(VehicleTrack).where(VehicleTrack.track_key == data["track_id"]))
    if track is None or track.source_type != "LIVE_FRAME":
        return None
    if not plate_key(data.get("final_text") or read("plate_number") or ""):
        return None
    return track


class MovementStore:
    def vehicle_movement_trail(self, vehicle_id, *, start=None, end=None, limit=30, offset=0):
        with self._lock as session:
            vehicle = session.get(Vehicle, vehicle_id)
            if vehicle is None:
                return None

            # Direct sightings use the persisted vehicle FK; captured plate text alone never attaches history.
            sightings = list(session.scalars(select(Sighting).where(
                Sighting.vehicle_id == vehicle_id, Sighting.observed_at.is_not(None))))
            events = []
            for row in sightings:
                payload = row.payload or {}
                events.append({"kind": "sighting", "id": row.id, "at": _at(row.observed_at),
                    "camera_id": payload.get("camera_id") or "", "camera_area": payload.get("camera_area") or "",
                    "association": "registry_linked", "sighting_key": row.record_key,
                    "status": row.status, "plate_number": payload.get("plate_number") or row.normalized_plate,
                    "latitude": payload.get("latitude"), "longitude": payload.get("longitude"),
                    "duty_verification": payload.get("duty_verification"),
                    "identity_evidence": "REGISTRY_LINK"})

            # A track is anchored only by a manually accepted recognition that produced a
            # sighting linked to this vehicle. Auto-accepted or plate-only matches do not anchor it.
            anchors = {}
            reviewed_sightings = {}
            r, d, s = Recognition.__table__, Detection.__table__, Sighting.__table__
            rows = session.execute(select(r, s.c.id.label("sighting_id")).join(d, d.c.recognition_id == r.c.id).join(
                s, s.c.detection_id == d.c.id).where(
                s.c.id.in_([item.id for item in sightings]), r.c.review_status == "ACCEPTED")).mappings()
            for recognition in rows:
                track = _reviewed_track(session, recognition)
                if track is not None:
                    anchors[track.id] = track
                    reviewed_sightings[recognition["sighting_id"]] = track
            for event in events:
                track = reviewed_sightings.get(event["id"])
                if track is not None:
                    event["identity_evidence"] = "MANUAL_REVIEW"
                    event["track_id"] = track.track_key

            tracks = dict(anchors)
            linked_ids = set()
            if anchors and scoped_department() is None:
                links = list(session.scalars(select(TrackLink).where(or_(
                    TrackLink.first_track_id.in_(anchors), TrackLink.second_track_id.in_(anchors)))))
                for link in links:
                    first = session.get(VehicleTrack, link.first_track_id)
                    second = session.get(VehicleTrack, link.second_track_id)
                    first_rec = session.get(Recognition, link.first_recognition_id)
                    second_rec = session.get(Recognition, link.second_recognition_id)
                    if not all((first, second, first_rec, second_rec)):
                        continue
                    first_reviewed = _reviewed_track(session, first_rec)
                    second_reviewed = _reviewed_track(session, second_rec)
                    if (first_reviewed is None or second_reviewed is None or
                            {first_reviewed.id, second_reviewed.id} != {first.id, second.id} or
                            plate_key((first_rec.payload or {}).get("final_text") or first_rec.plate_number) != link.normalized_plate or
                            plate_key((second_rec.payload or {}).get("final_text") or second_rec.plate_number) != link.normalized_plate):
                        continue
                    # A conflicting registry association must never be silently merged.
                    conflicts = session.scalars(select(Sighting.vehicle_id).join(
                        Detection, Sighting.detection_id == Detection.id).join(
                        Recognition, Detection.recognition_id == Recognition.id).where(
                        Recognition.payload["track_id"].as_string().in_((first.track_key, second.track_key)),
                        Sighting.vehicle_id.is_not(None), Sighting.vehicle_id != vehicle_id)).first()
                    if conflicts is not None:
                        continue
                    other = second if first.id in anchors else first
                    anchor = first if first.id in anchors else second
                    tracks[other.id] = other
                    if other.id not in anchors:
                        linked_ids.add(other.id)
                    events.append({"kind": "confirmed_link", "id": link.id,
                        "at": _at(second_rec.observed_at), "camera_id": second_reviewed.camera_id,
                        "from_camera_id": first_reviewed.camera_id, "to_camera_id": second_reviewed.camera_id,
                        "from_track_id": first_reviewed.track_key, "to_track_id": second_reviewed.track_key,
                        "association": "administrator_confirmed", "plate_number": link.normalized_plate,
                        "confirmed_by": link.confirmed_by, "confirmed_at": _at(link.confirmed_at),
                        "anchor_track_id": anchor.track_key})

            if tracks:
                crossings = session.execute(select(CheckpointCrossing, VehicleTrack).join(
                    VehicleTrack, VehicleTrack.id == CheckpointCrossing.track_id).where(
                    CheckpointCrossing.track_id.in_(tracks)))
                for crossing, track in crossings:
                    snapshot = crossing.line_snapshot or {}
                    events.append({"kind": "checkpoint_crossing", "id": crossing.id,
                        "at": _at(crossing.observed_at), "camera_id": track.camera_id,
                        "camera_area": "", "checkpoint_name": snapshot.get("name") or "Checkpoint",
                        "checkpoint_revision": crossing.revision, "direction": crossing.direction,
                        "track_id": track.track_key,
                        "association": "administrator_confirmed" if track.id in linked_ids else "reviewed_plate"})

            route_rows = session.scalars(select(ApprovedRoute).where(
                ApprovedRoute.department_id == vehicle.department_id,
                ApprovedRoute.active.is_(True),
                (ApprovedRoute.vehicle_id == vehicle.id) | ApprovedRoute.vehicle_id.is_(None)))
            routes = [route_dict(item) for item in route_rows]
            zones = [item.payload for item in session.scalars(select(Geofence))]
            findings = movement_findings(events, routes, zones,
                {"department_id": vehicle.department_id, "plate_number": vehicle.plate_number},
                lambda event: self.verify_vehicle_duty(vehicle.plate_number, moment(event["at"]),
                                                        event.get("camera_area") or "")) if routes else []
            if findings:
                reviews = {item.alert_key: item for item in session.scalars(select(MovementAlertReview).where(
                    MovementAlertReview.alert_key.in_(item["alert_key"] for item in findings)))}
                for item in findings:
                    review = reviews.get(item["alert_key"])
                    if review:
                        item.update(status=review.status, reviewed_by=review.reviewed_by,
                                    reviewed_at=_at(review.reviewed_at), notes=review.notes)

            # Keep source time visible; recorded-video processing times never become route evidence.
            if start:
                events = [row for row in events if row["at"] and moment(row["at"]) >= moment(start)]
                findings = [row for row in findings if moment(row["observed_at"]) >= moment(start)]
            if end:
                events = [row for row in events if row["at"] and moment(row["at"]) <= moment(end)]
                findings = [row for row in findings if moment(row["observed_at"]) <= moment(end)]
            events.sort(key=lambda row: (row["at"] or "", row["kind"], row["id"]), reverse=True)
            findings.sort(key=lambda row: (row["observed_at"], row["alert_key"]), reverse=True)
            return {"vehicle_id": vehicle_id, "total": len(events), "limit": limit,
                    "offset": offset, "items": events[offset:offset + limit],
                    "alert_total": len(findings), "alerts": findings,
                    "semantics": {"sighting": "registry_linked_record",
                                  "checkpoint_crossing": "reviewed_live_plate_or_confirmed_direct_link",
                                  "confirmed_link": "administrator_confirmed_pair_not_automatic_identity",
                                  "recorded_video": "excluded_from_track_associations"}}

    def review_movement_alert(self, vehicle_id: int, alert_key: str, status: str,
                              actor: str, notes: str) -> dict:
        if status not in {"CONFIRMED", "DISMISSED"}:
            raise ValueError("Review status must be CONFIRMED or DISMISSED")
        finding = next((item for item in (self.vehicle_movement_trail(vehicle_id) or {}).get("alerts", [])
                        if item["alert_key"] == alert_key), None)
        if finding is None:
            raise LookupError("Current movement alert not found")
        with self._lock as session:
            route = session.get(ApprovedRoute, finding["route_id"])
            vehicle = session.get(Vehicle, vehicle_id)
            if route is None or vehicle is None or route.revision != finding["route_revision"]:
                raise LookupError("Movement alert changed; reload before review")
            review = session.scalar(select(MovementAlertReview).where(
                MovementAlertReview.alert_key == alert_key))
            if review is None:
                review = MovementAlertReview(alert_key=alert_key, route_id=route.id,
                    vehicle_id=vehicle_id, status=status, reviewed_by=actor,
                    reviewed_at=get_local_now(), notes=notes)
                session.add(review)
            else:
                review.status, review.reviewed_by = status, actor
                review.reviewed_at, review.notes = get_local_now(), notes
            session.add(AuditEvent(occurred_at=get_local_now(), actor=actor,
                action="MOVEMENT_ALERT_REVIEWED", entity=alert_key,
                department_id=vehicle.department_id,
                details={"route_id": route.id, "vehicle_id": vehicle_id,
                         "finding_kind": finding["kind"], "status": status}))
            return {**finding, "status": status, "reviewed_by": actor,
                    "reviewed_at": _at(review.reviewed_at), "notes": notes}
