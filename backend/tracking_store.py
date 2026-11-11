"""Checkpoint configuration/counts and reviewed links between camera tracks."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from .config import LOCAL_TZ, get_local_now
from .db_models import CameraCheckpoint, CheckpointCrossing, Recognition, TrackLink, VehicleTrack
from .tracking import crossing_direction


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=LOCAL_TZ)


def plate_key(value: str) -> str:
    return "".join(char for char in value.upper() if char.isalnum())


class TrackingStore:
    @staticmethod
    def _checkpoint_dict(checkpoint: CameraCheckpoint) -> dict:
        return {"camera_id": checkpoint.camera_id, "name": checkpoint.name,
                "x1": checkpoint.x1, "y1": checkpoint.y1,
                "x2": checkpoint.x2, "y2": checkpoint.y2,
                "direction": checkpoint.direction, "active": checkpoint.active,
                "revision": checkpoint.revision}

    def get_camera_checkpoint(self, camera_id: str) -> dict | None:
        with self._lock as session:
            item = session.scalar(select(CameraCheckpoint).where(CameraCheckpoint.camera_id == camera_id))
            return self._checkpoint_dict(item) if item else None

    def save_camera_checkpoint(self, camera_id: str, config: dict) -> dict:
        if not camera_id or len(camera_id) > 100:
            raise ValueError("Camera ID must contain 1 to 100 characters")
        coords = [float(config[name]) for name in ("x1", "y1", "x2", "y2")]
        if any(not 0 <= value <= 1 for value in coords):
            raise ValueError("Checkpoint coordinates must be between 0 and 1")
        if (coords[0] - coords[2]) ** 2 + (coords[1] - coords[3]) ** 2 < 0.05 ** 2:
            raise ValueError("Checkpoint line is too short")
        direction = config.get("direction", "BOTH")
        if direction not in {"BOTH", "A_TO_B", "B_TO_A"}:
            raise ValueError("Invalid checkpoint direction")
        name = str(config.get("name", "Checkpoint")).strip()
        if not name or len(name) > 100:
            raise ValueError("Checkpoint name must contain 1 to 100 characters")
        values = dict(zip(("x1", "y1", "x2", "y2"), coords)) | {
            "name": name, "direction": direction, "active": bool(config.get("active", True))}
        with self._lock as session:
            item = session.scalar(select(CameraCheckpoint).where(CameraCheckpoint.camera_id == camera_id))
            if item is None:
                item = CameraCheckpoint(camera_id=camera_id, revision=1, **values)
                session.add(item)
            elif any(getattr(item, field) != value for field, value in values.items()):
                for field, value in values.items():
                    setattr(item, field, value)
                item.revision += 1
            session.flush()
            return self._checkpoint_dict(item)

    @staticmethod
    def _crossing(session, checkpoint: CameraCheckpoint | None, track: VehicleTrack,
                  previous: list[int] | None, current: list[int], event_id: int,
                  observed_at: datetime, width: int, height: int) -> dict | None:
        if checkpoint is None or not checkpoint.active or previous is None:
            return None
        direction = crossing_direction(previous, current, width, height,
                                       (checkpoint.x1, checkpoint.y1, checkpoint.x2, checkpoint.y2))
        if direction is None or (checkpoint.direction != "BOTH" and checkpoint.direction != direction):
            return None
        existing = session.scalar(select(CheckpointCrossing.id).where(
            CheckpointCrossing.checkpoint_id == checkpoint.id,
            CheckpointCrossing.revision == checkpoint.revision,
            CheckpointCrossing.track_id == track.id))
        if existing:
            return None
        session.add(CheckpointCrossing(
            checkpoint_id=checkpoint.id, track_id=track.id, event_id=event_id,
            observed_at=observed_at, direction=direction, revision=checkpoint.revision,
            line_snapshot=TrackingStore._checkpoint_dict(checkpoint),
        ))
        return {"track_id": track.track_key, "camera_id": checkpoint.camera_id,
                "direction": direction, "revision": checkpoint.revision,
                "timestamp": observed_at.isoformat()}

    def list_checkpoint_crossings(self, camera_id: str = "", limit: int = 100) -> list[dict]:
        with self._lock as session:
            query = select(CheckpointCrossing, VehicleTrack).join(
                VehicleTrack, VehicleTrack.id == CheckpointCrossing.track_id).order_by(
                CheckpointCrossing.id.desc()).limit(limit)
            if camera_id:
                query = query.where(VehicleTrack.camera_id == camera_id)
            return [{"track_id": track.track_key, "camera_id": track.camera_id,
                     "timestamp": item.observed_at.isoformat(), "direction": item.direction,
                     "revision": item.revision, "line_snapshot": item.line_snapshot}
                    for item, track in session.execute(query)]

    @staticmethod
    def _reviewed_record(session, recognition: Recognition):
        row = recognition.payload or {}
        if recognition.review_status != "ACCEPTED" or not row.get("reviewer"):
            return None
        key = row.get("track_id")
        plate = plate_key(row.get("final_text") or recognition.plate_number or "")
        if not key or not plate or recognition.observed_at is None:
            return None
        track = session.scalar(select(VehicleTrack).where(VehicleTrack.track_key == key))
        if track is None or track.source_type != "LIVE_FRAME":
            return None
        return recognition, track, plate, aware(recognition.observed_at)

    @staticmethod
    def _candidate(first, second, max_minutes: int) -> dict | None:
        if first[3] > second[3]:
            first, second = second, first
        if first[1].id == second[1].id or first[1].camera_id == second[1].camera_id or first[2] != second[2]:
            return None
        elapsed = int((second[3] - first[3]).total_seconds())
        if elapsed < 0 or elapsed > max_minutes * 60:
            return None
        return {"first_recognition_id": first[0].record_key,
                "second_recognition_id": second[0].record_key,
                "first_track_id": first[1].track_key, "second_track_id": second[1].track_key,
                "first_camera_id": first[1].camera_id, "second_camera_id": second[1].camera_id,
                "plate_number": first[2], "first_seen": first[3].isoformat(),
                "second_seen": second[3].isoformat(), "elapsed_seconds": elapsed}

    def cross_camera_candidates(self, max_minutes: int = 180, lookback_days: int = 7,
                                limit: int = 100) -> list[dict]:
        with self._lock as session:
            rows = list(session.scalars(select(Recognition).where(
                Recognition.review_status == "ACCEPTED",
                Recognition.observed_at >= get_local_now() - timedelta(days=lookback_days),
            ).order_by(Recognition.observed_at.desc()).limit(500)))
            reviewed = [item for row in rows if (item := self._reviewed_record(session, row))]
            reviewed.sort(key=lambda item: item[3])
            best = {}
            for index, second in enumerate(reviewed):
                for first in reversed(reviewed[:index]):
                    if second[3] - first[3] > timedelta(minutes=max_minutes):
                        break
                    candidate = self._candidate(first, second, max_minutes)
                    if candidate is None:
                        continue
                    pair = tuple(sorted((first[1].id, second[1].id)))
                    if pair not in best or candidate["elapsed_seconds"] < best[pair]["elapsed_seconds"]:
                        best[pair] = candidate
            links = {(link.first_track_id, link.second_track_id) for link in session.scalars(select(TrackLink))}
            results = []
            for pair, candidate in best.items():
                results.append({**candidate, "confirmed": pair in links})
            return sorted(results, key=lambda item: item["second_seen"], reverse=True)[:limit]

    def confirm_cross_camera_link(self, first_key: str, second_key: str,
                                  actor: str, max_minutes: int = 180) -> dict:
        with self._lock as session:
            first_row = session.scalar(select(Recognition).where(Recognition.record_key == first_key))
            second_row = session.scalar(select(Recognition).where(Recognition.record_key == second_key))
            if first_row is None or second_row is None:
                raise LookupError("Recognition not found")
            first = self._reviewed_record(session, first_row)
            second = self._reviewed_record(session, second_row)
            candidate = self._candidate(first, second, max_minutes) if first and second else None
            if candidate is None:
                raise ValueError("A confirmed link requires reviewed matching live plates from different cameras within the time window")
            first_track, second_track = sorted((first[1], second[1]), key=lambda item: item.id)
            existing = session.scalar(select(TrackLink).where(
                TrackLink.first_track_id == first_track.id,
                TrackLink.second_track_id == second_track.id))
            if existing is None:
                ordered_recognitions = (first_row, second_row) if first[3] <= second[3] else (second_row, first_row)
                link = TrackLink(first_track_id=first_track.id, second_track_id=second_track.id,
                    first_recognition_id=ordered_recognitions[0].id,
                    second_recognition_id=ordered_recognitions[1].id,
                    normalized_plate=candidate["plate_number"],
                    elapsed_seconds=candidate["elapsed_seconds"],
                    confirmed_by=actor, confirmed_at=get_local_now())
                session.add(link)
                session.flush()
                existing = link
            return {**candidate, "confirmed": True, "confirmed_by": existing.confirmed_by,
                    "confirmed_at": existing.confirmed_at.isoformat()}

    def list_cross_camera_links(self, limit: int = 100) -> list[dict]:
        with self._lock as session:
            links = session.scalars(select(TrackLink).order_by(TrackLink.id.desc()).limit(limit))
            return [{"first_track_id": session.get(VehicleTrack, row.first_track_id).track_key,
                     "second_track_id": session.get(VehicleTrack, row.second_track_id).track_key,
                     "plate_number": row.normalized_plate,
                     "elapsed_seconds": row.elapsed_seconds,
                     "confirmed_by": row.confirmed_by,
                     "confirmed_at": row.confirmed_at.isoformat()}
                    for row in links]
