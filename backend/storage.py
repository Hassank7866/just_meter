from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from .config import get_local_now, settings
from .database import get_engine, TransactionLock
from .db_records import Records
from .risk_store import RiskStore
from .dashboard import DashboardStore
from .vims_store import VimsStore
from .duty_store import DutyStore
from .digital_twin import DigitalTwinStore
from .movement import MovementStore
from .route_store import RouteStore
from .vehicle_verification import VehicleVerificationStore
from .challan_store import ChallanStore
from .duty_verification import merge_duty
from .db_models import CameraCheckpoint, CheckpointCrossing, Challan, Detection, Sighting, TrackLink, Vehicle, Recognition, VehicleEvent, VehicleTrack, TrackObservation
from .tracking import associate
from .tracking_store import TrackingStore
from sqlalchemy import select, func
from datetime import timedelta

HEADERS = ["timestamp", "camera_area", "plate_number", "confidence", "latitude", "longitude", "location_accuracy_m", "vehicle_type", "image", "bbox"]
APPROVED_HEADERS = [
    "plate_number",
    "vehicle_id",
    "department",
    "authorized_areas",
    "duty_schedule",
    "notes",
    "officer_name",
    "officer_phone",
    "officer_email",
    "risk_context",
]
GOVERNMENT_HEADERS = HEADERS + [
    "vehicle_id",
    "department",
    "authorized_areas",
    "duty_schedule",
    "status",
    "violation_criteria",
    "violation_id",
    "notes",
    "decision_reason",
    "decision_rules",
    "violation_count",
    "risk_score",
    "risk_level",
    "risk_factors",
]
VEHICLE_EVENT_HEADERS = [
    "event_id", "timestamp", "camera_id", "camera_area", "source_type",
    "frame_number", "frame_width", "frame_height", "vehicle_count",
    "model_name", "model_version", "detections_json",
]
PLATE_RECOGNITION_HEADERS = [
    "recognition_id", "detection_event_id", "timestamp", "camera_id", "camera_area",
    "raw_text", "normalized_text", "suggested_text", "final_text", "confidence",
    "valid_format", "review_status", "review_reason", "plate_crop", "bbox",
    "ocr_model", "reviewer", "reviewed_at", "review_notes",
]
EVIDENCE_HEADERS = [
    "evidence_id", "detection_event_id", "recognition_id", "timestamp", "camera_id",
    "camera_area", "plate_number", "ocr_confidence", "vehicle_type", "department",
    "full_image", "plate_crop", "full_image_sha256", "plate_crop_sha256",
    "full_image_size", "plate_crop_size", "frame_width", "frame_height", "latitude",
    "longitude", "review_status", "case_status", "integrity_status", "related_violation_id",
    "related_challan_id", "reviewer", "reviewed_at", "review_notes",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_plate(plate: str) -> str:
    """Match plates regardless of spaces, hyphens, punctuation, or letter case."""
    return "".join(char for char in plate.upper() if char.isalnum())


class DetectionStore(Records, TrackingStore, MovementStore, RouteStore, VehicleVerificationStore, RiskStore, DashboardStore, VimsStore, DutyStore, DigitalTwinStore, ChallanStore):
    def __init__(self, engine=None) -> None:
        self.engine = engine if engine is not None else get_engine()
        self._lock = TransactionLock(self.engine)
        settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
        settings.plate_crops_dir.mkdir(parents=True, exist_ok=True)
        settings.evidence_images_dir.mkdir(parents=True, exist_ok=True)

    def save_evidence(
        self, frame: np.ndarray, detection_event: dict, recognition: dict,
        plate: dict, latitude: float | None, longitude: float | None,
        vehicle_type: str | None = None, approved_vehicle: dict | None = None,
        compliance: dict | None = None,
    ) -> dict:
        """Archive immutable image files and their integrity metadata."""
        evidence_id = f"EVD-{uuid4().hex[:12].upper()}"
        event_id = detection_event["event_id"]
        full_relative = f"evidence/{event_id}.jpg"
        full_path = settings.snapshots_dir / full_relative
        if not full_path.exists() and not cv2.imwrite(str(full_path), frame):
            raise RuntimeError("Could not archive evidence frame")
        crop_relative = recognition.get("plate_crop", "")
        crop_path = settings.snapshots_dir / crop_relative if crop_relative else None
        crop_exists = bool(crop_path and crop_path.exists())
        violation_id = (compliance or {}).get("violation_id", "")
        challan_id = (compliance or {}).get("challan_id", "")
        row = {
            "evidence_id": evidence_id,
            "detection_event_id": event_id,
            "recognition_id": recognition["recognition_id"],
            "track_id": recognition.get("track_id", ""),
            "timestamp": recognition["timestamp"],
            "camera_id": detection_event["camera_id"],
            "camera_area": detection_event["camera_area"],
            "plate_number": recognition.get("final_text") or recognition.get("normalized_text") or plate.get("plate_number", ""),
            "ocr_confidence": plate.get("confidence", ""),
            "vehicle_type": vehicle_type or "",
            "department": (approved_vehicle or {}).get("department", ""),
            "full_image": full_relative,
            "plate_crop": crop_relative,
            "full_image_sha256": sha256_file(full_path),
            "plate_crop_sha256": sha256_file(crop_path) if crop_exists else "",
            "full_image_size": full_path.stat().st_size,
            "plate_crop_size": crop_path.stat().st_size if crop_exists else 0,
            "frame_width": frame.shape[1],
            "frame_height": frame.shape[0],
            "latitude": "" if latitude is None else latitude,
            "longitude": "" if longitude is None else longitude,
            "review_status": "CAPTURED",
            "case_status": "ATTACHED_TO_CHALLAN" if challan_id else "ATTACHED_TO_VIOLATION" if violation_id else "UNASSIGNED",
            "integrity_status": "VERIFIED",
            "related_violation_id": violation_id,
            "related_challan_id": challan_id,
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
            **({"duty_verification": compliance["duty_verification"]} if (compliance or {}).get("duty_verification") else {}),
        }
        self._append("evidence_path", row)
        return row

    def get_evidence_records(
        self, query: str | None = None, status: str | None = None, limit: int = 500,
        review_status: str | None = None, case_status: str | None = None,
    ) -> list[dict]:
        with self._lock:
            source = self._rows("evidence_path")
            rows = list(source)
        if status:
            if status.upper() in {"CAPTURED", "UNDER_REVIEW", "VERIFIED"}:
                review_status = status
            elif status.upper() in {"UNASSIGNED", "ATTACHED_TO_VIOLATION", "ATTACHED_TO_CHALLAN"}:
                case_status = status
        if review_status:
            rows = [row for row in rows if row.get("review_status") == review_status.upper()]
        if case_status:
            rows = [row for row in rows if row.get("case_status") == case_status.upper()]
        if query:
            needle = query.strip().lower()
            rows = [row for row in rows if any(needle in row.get(key, "").lower() for key in (
                "evidence_id", "detection_event_id", "recognition_id", "plate_number",
                "camera_id", "camera_area", "department",
            ))]
        return list(reversed(rows[-limit:]))

    def get_evidence(self, evidence_id: str) -> dict | None:
        records = self._rows("evidence_path")
        return next((row for row in records if row.get("evidence_id") == evidence_id), None)

    def get_evidence_for_recognition(self, recognition_id: str) -> dict | None:
        with self._lock:
            source = self._rows("evidence_path")
            return next((row for row in source
                         if row.get("recognition_id") == recognition_id), None)

    def update_reviewed_evidence(
        self, recognition_id: str, plate_number: str, department: str,
        vehicle_type: str, violation_id: str = "", challan_id: str = "",
    ) -> dict | None:
        """Associate an archived uncertain read with its corrected plate and case."""
        with self._lock:
            with self._lock:
                source = self._rows("evidence_path")
                rows = list(source)
            updated = None
            for row in rows:
                if row.get("recognition_id") != recognition_id:
                    continue
                row["plate_number"] = plate_number
                row["department"] = department
                row["vehicle_type"] = vehicle_type or row.get("vehicle_type", "")
                row["related_violation_id"] = violation_id
                row["related_challan_id"] = challan_id
                row["case_status"] = (
                    "ATTACHED_TO_CHALLAN" if challan_id else
                    "ATTACHED_TO_VIOLATION" if violation_id else "UNASSIGNED"
                )
                updated = row
                break
            if updated is not None:
                self._replace("evidence_path", rows)
            return updated

    def verify_evidence(self, evidence_id: str) -> dict | None:
        record = self.get_evidence(evidence_id)
        if record is None:
            return None
        results = {}
        for label, path_key, hash_key in (
            ("full_image", "full_image", "full_image_sha256"),
            ("plate_crop", "plate_crop", "plate_crop_sha256"),
        ):
            relative = record.get(path_key, "")
            path = settings.snapshots_dir / relative if relative else None
            exists = bool(path and path.exists())
            actual = sha256_file(path) if exists else ""
            expected = record.get(hash_key, "")
            results[label] = {"exists": exists, "expected_sha256": expected, "actual_sha256": actual, "valid": exists and actual == expected}
        overall = all(item["valid"] for item in results.values() if item["expected_sha256"])
        if not record.get("plate_crop_sha256"):
            overall = results["full_image"]["valid"]
        integrity_status = "VERIFIED" if overall else "FAILED"
        with self._lock:
            with self._lock:
                source = self._rows("evidence_path")
                rows = list(source)
            changed = False
            for row in rows:
                if row.get("evidence_id") == evidence_id:
                    row["integrity_status"] = integrity_status
                    changed = True
                    break
            if changed:
                self._replace("evidence_path", rows)
        return {
            "evidence_id": evidence_id, "integrity_status": integrity_status,
            "valid": overall, "files": results,
        }

    def review_evidence(
        self, evidence_id: str, review_status: str, reviewer: str, notes: str,
    ) -> dict | None:
        with self._lock:
            with self._lock:
                source = self._rows("evidence_path")
                rows = list(source)
            updated = None
            for row in rows:
                if row.get("evidence_id") == evidence_id:
                    if review_status == "VERIFIED" and row.get("review_status") != "UNDER_REVIEW":
                        raise ValueError("Evidence must be UNDER_REVIEW before review can be completed")
                    row["review_status"] = review_status
                    row["reviewer"] = reviewer
                    row["reviewed_at"] = get_local_now().isoformat()
                    row["review_notes"] = notes
                    updated = row
                    break
            if updated is None:
                return None
            self._replace("evidence_path", rows)
            return updated

    def save_plate_recognition(
        self, frame: np.ndarray, plate: dict, analysis: dict, detection_event_id: str,
        camera_id: str, camera_area: str, track_id: str = "",
    ) -> dict:
        recognition_id = f"ANPR-{uuid4().hex[:12].upper()}"
        now = get_local_now()
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = [int(v) for v in plate["bbox"]]
        x1, x2 = max(0, min(x1, width)), max(0, min(x2, width))
        y1, y2 = max(0, min(y1, height)), max(0, min(y2, height))
        crop_name = ""
        if x2 > x1 and y2 > y1:
            crop_name = f"plates/{recognition_id}.jpg"
            cv2.imwrite(str(settings.snapshots_dir / crop_name), frame[y1:y2, x1:x2])
        row = {
            "recognition_id": recognition_id,
            "detection_event_id": detection_event_id,
            "timestamp": now.isoformat(),
            "camera_id": camera_id,
            "camera_area": camera_area,
            "track_id": track_id,
            "raw_text": analysis["raw_text"],
            "normalized_text": analysis["normalized_text"],
            "suggested_text": analysis.get("suggested_text") or "",
            "final_text": analysis.get("final_text") or "",
            "confidence": plate["confidence"],
            "valid_format": str(bool(analysis["valid_format"])).lower(),
            "review_status": analysis["review_status"],
            "review_reason": analysis["review_reason"],
            "plate_crop": crop_name,
            "bbox": ",".join(map(str, plate["bbox"])),
            "ocr_model": "cct-xs-v2-global-model",
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
        }
        self._append("plate_recognition_path", row)
        return row

    def get_plate_recognitions(self, status: str | None = None, limit: int = 200) -> list[dict]:
        with self._lock:
            source = self._rows("plate_recognition_path")
            rows = list(source)
        if status:
            rows = [row for row in rows if row.get("review_status") == status.upper()]
        return list(reversed(rows[-limit:]))

    def get_plate_recognition(self, recognition_id: str) -> dict | None:
        with self._lock:
            source = self._rows("plate_recognition_path")
            return next((row for row in source
                         if row.get("recognition_id") == recognition_id), None)

    def review_plate_recognition(
        self, recognition_id: str, corrected_text: str, status: str, reviewer: str, notes: str,
    ) -> dict | None:
        with self._lock:
            with self._lock:
                source = self._rows("plate_recognition_path")
                rows = list(source)
            updated = None
            for row in rows:
                if row.get("recognition_id") == recognition_id:
                    row["review_status"] = status
                    row["final_text"] = corrected_text if status == "ACCEPTED" else ""
                    row["reviewer"] = reviewer
                    row["reviewed_at"] = get_local_now().isoformat()
                    row["review_notes"] = notes
                    updated = row
                    break
            if updated is None:
                return None
            self._replace("plate_recognition_path", rows)
            return updated

    def save_vehicle_event(
        self,
        vehicles: list[dict],
        camera_id: str,
        camera_area: str,
        source_type: str,
        frame_width: int,
        frame_height: int,
        frame_number: int | None = None,
        stream_id: str | None = None,
        max_frame_gap: int = 60,
    ) -> dict:
        """Persist boxes and assign per-stream track identities atomically."""
        observed_at = get_local_now()
        camera_id = camera_id.strip()
        # Recorded uploads need their own stream ID; the caller supplies one per upload.
        stream_id = stream_id or (camera_id if source_type == "LIVE_FRAME" else f"VIDEO-{uuid4().hex}")
        event = {
            "event_id": f"DET-{uuid4().hex[:12].upper()}",
            "timestamp": observed_at.isoformat(),
            "camera_id": camera_id,
            "camera_area": camera_area,
            "source_type": source_type,
            "frame_number": "" if frame_number is None else frame_number,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "vehicle_count": len(vehicles),
            "model_name": "yolo11n.pt",
            "model_version": "YOLO11",
            "stream_id": stream_id,
            "detections_json": "[]",
        }
        with self._lock as session:
            saved_event = self._upsert(session, "vehicle_events_path", event)
            query = select(VehicleTrack).where(
                VehicleTrack.camera_id == camera_id,
                VehicleTrack.stream_id == stream_id,
            )
            # Video frames use source frame numbers; inference runtime is irrelevant.
            if source_type == "LIVE_FRAME":
                query = query.where(VehicleTrack.last_seen >= observed_at - timedelta(seconds=4))
            recent = list(session.scalars(query))
            recent = [track for track in recent if frame_number is None or
                      track.last_frame_number is None or
                      0 < frame_number - track.last_frame_number <= max_frame_gap]
            matches = associate(vehicles, recent)
            checkpoint = session.scalar(select(CameraCheckpoint).where(CameraCheckpoint.camera_id == camera_id))
            tracked = []
            new_count = 0
            crossings = []
            for index, vehicle in enumerate(vehicles):
                track = matches.get(index)
                previous_bbox = None
                if track is None:
                    new_count += 1
                    track = VehicleTrack(
                        track_key=f"TRK-{uuid4().hex[:12].upper()}", camera_id=camera_id,
                        stream_id=stream_id, source_type=source_type, label=vehicle["label"],
                        first_seen=observed_at, last_seen=observed_at,
                        first_event_id=saved_event.id, last_event_id=saved_event.id,
                        last_frame_number=frame_number, last_bbox=vehicle["bbox"],
                        observation_count=0,
                    )
                    session.add(track)
                    session.flush([track])
                else:
                    previous_event = session.get(VehicleEvent, track.last_event_id)
                    if previous_event and int(previous_event.payload.get("frame_width") or 0) == frame_width and \
                            int(previous_event.payload.get("frame_height") or 0) == frame_height:
                        previous_bbox = track.last_bbox
                crossing = self._crossing(session, checkpoint, track, previous_bbox, vehicle["bbox"],
                                          saved_event.id, observed_at, frame_width, frame_height)
                if crossing:
                    crossings.append(crossing)
                track.last_seen = observed_at
                track.last_event_id = saved_event.id
                track.last_frame_number = frame_number
                track.last_bbox = vehicle["bbox"]
                track.observation_count += 1
                session.add(TrackObservation(
                    track_id=track.id, event_id=saved_event.id, detection_index=index,
                    observed_at=observed_at, frame_number=frame_number, bbox=vehicle["bbox"],
                ))
                tracked.append({**vehicle, "track_id": track.track_key})
            event["detections_json"] = json.dumps(tracked, separators=(",", ":"))
            event["new_track_count"] = new_count
            event["new_crossing_count"] = len(crossings)
            saved_event.payload = {**saved_event.payload, **event}
        return {**event, "detections": tracked, "crossings": crossings}

    def latest_vehicle_tracks(self, camera_id: str = "", limit: int = 100) -> list[dict]:
        with self._lock as session:
            query = select(VehicleTrack).order_by(VehicleTrack.id.desc()).limit(limit)
            if camera_id:
                query = query.where(VehicleTrack.camera_id == camera_id)
            return [self._track_summary(track) for track in session.scalars(query)]

    @staticmethod
    def _track_summary(track: VehicleTrack) -> dict:
        return {
            "track_id": track.track_key, "camera_id": track.camera_id,
            "stream_id": track.stream_id, "source_type": track.source_type,
            "label": track.label, "first_seen": track.first_seen.isoformat(),
            "last_seen": track.last_seen.isoformat(),
            "last_frame_number": track.last_frame_number,
            "last_bbox": track.last_bbox, "observation_count": track.observation_count,
        }

    def vehicle_track_details(self, track_key: str) -> dict | None:
        with self._lock as session:
            track = session.scalar(select(VehicleTrack).where(VehicleTrack.track_key == track_key))
            if track is None:
                return None
            observations = session.scalars(select(TrackObservation).where(
                TrackObservation.track_id == track.id).order_by(TrackObservation.id))
            crossings = list(session.scalars(select(CheckpointCrossing).where(
                CheckpointCrossing.track_id == track.id).order_by(CheckpointCrossing.id)))
            links = list(session.scalars(select(TrackLink).where(
                (TrackLink.first_track_id == track.id) | (TrackLink.second_track_id == track.id))))
            return {**self._track_summary(track), "observations": [
                {"event_id": session.get(VehicleEvent, item.event_id).record_key,
                 "frame_number": item.frame_number, "observed_at": item.observed_at.isoformat(),
                 "bbox": item.bbox}
                for item in observations
            ], "crossings": [{"timestamp": item.observed_at.isoformat(),
                              "direction": item.direction, "revision": item.revision,
                              "line_snapshot": item.line_snapshot} for item in crossings],
                "linked_tracks": [{"track_id": session.get(VehicleTrack,
                    item.second_track_id if item.first_track_id == track.id else item.first_track_id).track_key,
                    "plate_number": item.normalized_plate,
                    "confirmed_at": item.confirmed_at.isoformat()} for item in links]}

    def latest_vehicle_events(self, limit: int = 100) -> list[dict]:
        with self._lock:
            source = self._rows("vehicle_events_path")
            rows = list(source)
        results = []
        for row in reversed(rows[-limit:]):
            try:
                detections = json.loads(row.pop("detections_json", "[]"))
            except json.JSONDecodeError:
                detections = []
            results.append({**row, "vehicle_count": int(row.get("vehicle_count") or 0), "detections": detections})
        return results

    def is_duplicate(self, plate: str, now: datetime, camera_area: str = "") -> bool:
        with self._lock as session:
            start = now - timedelta(seconds=settings.duplicate_cooldown_seconds)
            end = now + timedelta(seconds=settings.duplicate_cooldown_seconds)
            if settings.duplicate_cooldown_seconds <= 0:
                return False
            previous = session.scalars(select(Detection).where(
                Detection.normalized_plate == normalize_plate(plate),
                Detection.observed_at > start, Detection.observed_at < end))
            return any(item.payload.get("camera_id", item.payload.get("camera_area", "")) == camera_area for item in previous)

    def find_approved_vehicle(self, plate_number: str) -> dict[str, str] | None:
        target = normalize_plate(plate_number)
        if not target:
            return None
        with self._lock:
            source = self._rows("approved_vehicles_path")
            for row in source:
                if normalize_plate(row.get("plate_number", "")) == target:
                    return {key: row.get(key, "") for key in APPROVED_HEADERS}
        return None

    def save(self, frame: np.ndarray, plate: dict, latitude: float | None, longitude: float | None,
             accuracy: float | None, vehicle_type: str | None, camera_area: str,
             approved_vehicle: dict[str, str] | None = None,
             compliance: dict | None = None,
             event_timestamp: datetime | None = None) -> tuple[bool, str | None]:
        now = get_local_now()
        detected_at = event_timestamp or now
        normalized = normalize_plate(plate["plate_number"])
        record_key = plate.get("recognition_id") or uuid4().hex
        recognition = self.get_plate_recognition(plate.get("recognition_id", ""))
        camera_id = (recognition or {}).get("camera_id") or camera_area
        with self._lock as session:
            recognition_pk = self._lookup(session, Recognition, plate.get("recognition_id"))
            already_processed = session.scalar(select(Detection.id).where(Detection.record_key == record_key))
            if recognition_pk:
                already_processed = already_processed or session.scalar(select(Detection.id).where(Detection.recognition_id == recognition_pk))
            if already_processed:
                return False, "recognition already processed"
            if self.is_duplicate(normalized, detected_at, camera_id):
                return False, "duplicate within cooldown"
            policy = result = None
            if approved_vehicle and compliance:
                if "base_compliance" in compliance:
                    duty = self.verify_vehicle_duty(plate["plate_number"], detected_at, camera_area)
                    compliance.update(merge_duty(compliance["base_compliance"], duty))
                policy, result = self._score_current_risk(session, compliance, normalized, detected_at, approved_vehicle)
                compliance.update(result)
            safe_plate = normalized[:32] or "unknown"
            filename = f"{safe_plate}_{uuid4().hex}.jpg"
            if not cv2.imwrite(str(settings.snapshots_dir / filename), frame):
                raise RuntimeError("Could not write snapshot")
            row = {
                "_record_key": record_key, "recognition_id": plate.get("recognition_id", ""),
                "track_id": plate.get("track_id", ""),
                "timestamp": detected_at.isoformat(), "plate_number": plate["plate_number"],
                "camera_area": camera_area, "camera_id": camera_id,
                "confidence": plate["confidence"], "latitude": latitude, "longitude": longitude,
                "location_accuracy_m": accuracy, "vehicle_type": vehicle_type or "",
                "image": filename, "bbox": ",".join(map(str, plate["bbox"])),
            }
            self._append("csv_path", row)
            if approved_vehicle:
                violation_id = f"VIOL-{record_key}" if compliance and compliance.get("status") == "VIOLATION" else ""
                prior_count = session.scalar(select(func.count()).select_from(Sighting).where(
                    Sighting.normalized_plate == normalized, Sighting.status == "VIOLATION")) or 0
                government_row = row | {
                    "detection_key": record_key,
                    "vehicle_id": approved_vehicle.get("vehicle_id", ""),
                    "department": approved_vehicle.get("department", ""),
                    "authorized_areas": approved_vehicle.get("authorized_areas", ""),
                    "duty_schedule": approved_vehicle.get("duty_schedule", ""),
                    "status": compliance["status"] if compliance else "UNASSESSED",
                    "violation_criteria": (compliance or {}).get("violation_criteria", ""),
                    "violation_id": violation_id, "notes": approved_vehicle.get("notes", ""),
                    "decision_reason": (compliance or {}).get("decision_reason", ""),
                    "decision_rules": json.dumps((compliance or {}).get("rules", [])),
                    **({"base_compliance": compliance["base_compliance"], "duty_verification": compliance["duty_verification"]}
                       if (compliance or {}).get("duty_verification") else {}),
                    "violation_count": prior_count + bool(violation_id),
                    **(result or {}),
                    "risk_factors": json.dumps((result or {}).get("risk_factors", [])),
                }
                sighting = self._append("government_sightings_path", government_row)
                self._capture_verification(session, sighting, vehicle_type or "")
                if result is not None:
                    self._persist_risk(session, sighting, policy, result)
                if violation_id:
                    self._ensure_challan_draft(session, sighting)
        return True, None

    def _attach_evidence_to_challan(self, violation_ids: set[str], challan_id: str) -> None:
        if not violation_ids:
            return
        with self._lock:
            source = self._rows("evidence_path")
            evidence = list(source)
        changed = False
        for record in evidence:
            if record.get("related_violation_id") in violation_ids:
                record["related_challan_id"] = challan_id
                record["case_status"] = "ATTACHED_TO_CHALLAN"
                changed = True
        if changed:
            self._replace("evidence_path", evidence)

    def attach_evidence_to_vehicle_challan(self, plate_number: str, challan_id: str) -> None:
        target = normalize_plate(plate_number)
        if not target or not challan_id:
            return
        with self._lock:
            source = self._rows("government_sightings_path")
            violation_ids = {
                row.get("violation_id", "")
                for row in source
                if row.get("status") == "VIOLATION"
                and normalize_plate(row.get("plate_number", "")) == target
            }
            self._attach_evidence_to_challan(violation_ids, challan_id)

    def latest(self, limit: int) -> list[dict]:
        with self._lock:
            source = self._rows("csv_path")
            rows = list(source)
        return list(reversed(rows[-limit:]))

    def latest_government_sightings(self, limit: int = 1000) -> list[dict]:
        with self._lock:
            source = self._rows("government_sightings_path")
            rows = list(source)
        return list(reversed(rows[-limit:]))

    def get_all_approved_vehicles(self, query: str | None = None, area: str | None = None) -> list[dict]:
        with self._lock:
            source = self._rows("approved_vehicles_path")
            rows = list(source)

        results = []
        q = (query or "").strip().lower()
        target_area = (area or "").strip()

        for r in rows:
            # Ensure all keys from APPROVED_HEADERS are present
            row_dict = {key: r.get(key, "") for key in APPROVED_HEADERS}
            if q:
                match = (
                    q in row_dict.get("plate_number", "").lower()
                    or q in row_dict.get("vehicle_id", "").lower()
                    or q in row_dict.get("department", "").lower()
                    or q in row_dict.get("notes", "").lower()
                    or q in row_dict.get("officer_name", "").lower()
                    or q in row_dict.get("officer_phone", "").lower()
                    or q in row_dict.get("officer_email", "").lower()
                )
                if not match:
                    continue
            if target_area and target_area != "ALL":
                areas = [a.strip() for a in row_dict.get("authorized_areas", "").split("|")]
                if target_area not in areas:
                    continue
            results.append(row_dict)
        return results

    def add_approved_vehicle(self, record: dict) -> tuple[bool, str | None]:
        plate = record.get("plate_number", "").strip()
        if not plate:
            return False, "Plate number is required"
        target = normalize_plate(plate)

        with self._lock as session:
            linked = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == target))
            if linked is not None and linked.vims_source_id is not None:
                return False, "This vehicle is managed by VIMS; update it through a synchronization import"
            rows = []
            with self._lock:
                source = self._rows("approved_vehicles_path")
                rows = list(source)

            for r in rows:
                if normalize_plate(r.get("plate_number", "")) == target:
                    return False, f"Vehicle with plate '{plate}' already exists in registry"

            new_row = {
                "plate_number": plate,
                "vehicle_id": record.get("vehicle_id", "").strip(),
                "department": record.get("department", "").strip(),
                "authorized_areas": record.get("authorized_areas", "").strip(),
                "duty_schedule": record.get("duty_schedule", "").strip() or "24/7",
                "notes": record.get("notes", "").strip(),
                "officer_name": record.get("officer_name", "").strip(),
                "officer_phone": record.get("officer_phone", "").strip(),
                "officer_email": record.get("officer_email", "").strip(),
                "risk_context": record.get("risk_context", "").strip(),
            }
            rows.append(new_row)

            self._replace("approved_vehicles_path", rows)

        return True, None

    def update_approved_vehicle(self, original_plate: str, updated_record: dict) -> tuple[bool, str | None]:
        target = normalize_plate(original_plate)
        if not target:
            return False, "Invalid target plate number"

        new_plate = updated_record.get("plate_number", "").strip() or original_plate
        new_target = normalize_plate(new_plate)

        with self._lock as session:
            linked = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == target))
            if linked is not None and linked.vims_source_id is not None:
                controlled = ("plate_number", "vehicle_id", "department", "authorized_areas", "duty_schedule")
                if any(key in updated_record and updated_record[key] != linked.payload.get(key, "") for key in controlled):
                    return False, "VIMS registry fields must be updated through a synchronization import"
            rows = []
            with self._lock:
                source = self._rows("approved_vehicles_path")
                rows = list(source)

            # Check if new_plate conflicts with another entry
            if new_target != target:
                for r in rows:
                    if normalize_plate(r.get("plate_number", "")) == new_target:
                        return False, f"Another vehicle already exists with plate '{new_plate}'"

            found = False
            for idx, r in enumerate(rows):
                if normalize_plate(r.get("plate_number", "")) == target:
                    rows[idx] = {**r,
                        "plate_number": new_plate,
                        "vehicle_id": updated_record.get("vehicle_id", r.get("vehicle_id", "")).strip(),
                        "department": updated_record.get("department", r.get("department", "")).strip(),
                        "authorized_areas": updated_record.get("authorized_areas", r.get("authorized_areas", "")).strip(),
                        "duty_schedule": updated_record.get("duty_schedule", r.get("duty_schedule", "")).strip() or "24/7",
                        "notes": updated_record.get("notes", r.get("notes", "")).strip(),
                        "officer_name": updated_record.get("officer_name", r.get("officer_name", "")).strip(),
                        "officer_phone": updated_record.get("officer_phone", r.get("officer_phone", "")).strip(),
                        "officer_email": updated_record.get("officer_email", r.get("officer_email", "")).strip(),
                        "risk_context": updated_record.get("risk_context", r.get("risk_context", "")).strip(),
                    }
                    found = True
                    break

            if not found:
                return False, f"Vehicle with plate '{original_plate}' not found in registry"

            if new_target != target:
                original = session.scalar(select(Vehicle).where(Vehicle.record_key == target))
                existing = session.scalar(select(Vehicle.id).where(Vehicle.record_key == new_target))
                if existing is not None:
                    return False, "Plate belongs to an existing or archived vehicle"
                original.record_key = new_target
                original.normalized_plate = new_target
                session.flush()
            self._replace("approved_vehicles_path", rows)

        return True, None

    def delete_approved_vehicle(self, plate_number: str) -> tuple[bool, str | None]:
        target = normalize_plate(plate_number)
        if not target:
            return False, "Invalid plate number"

        with self._lock as session:
            linked = session.scalar(select(Vehicle).where(Vehicle.normalized_plate == target))
            if linked is not None and linked.vims_source_id is not None:
                return False, "This vehicle is managed by VIMS; deactivate it through a synchronization import"
            rows = []
            with self._lock:
                source = self._rows("approved_vehicles_path")
                rows = list(source)

            filtered = [r for r in rows if normalize_plate(r.get("plate_number", "")) != target]
            if len(filtered) == len(rows):
                return False, f"Vehicle with plate '{plate_number}' not found"

            self._replace("approved_vehicles_path", filtered)

        return True, None

    def get_violations_summary(self, query: str | None = None, stage: str | None = None) -> list[dict]:
        """Aggregate stable vehicle identities; four violations indicate eligibility, not issuance."""
        with self._lock as session:
            sightings = []
            for row in session.scalars(select(Sighting).order_by(Sighting.id)):
                sightings.append(dict(row.payload) | {"_vehicle_database_id": row.vehicle_id, "status": row.status})

            approved_map: dict[str, dict] = {}
            with self._lock:
                for vehicle in session.scalars(select(Vehicle)):
                    approved_map[str(vehicle.id)] = {k: vehicle.payload.get(k, "") for k in APPROVED_HEADERS}
                    approved_map[str(vehicle.id)]["plate_number"] = vehicle.plate_number

        # Filter violations only
        violations_by_plate: dict[str, list[dict]] = {}
        for s in sightings:
            if s.get("status") == "VIOLATION":
                p_norm = str(s["_vehicle_database_id"]) if s.get("_vehicle_database_id") else normalize_plate(s.get("plate_number", ""))
                if not p_norm:
                    continue
                if p_norm not in violations_by_plate:
                    violations_by_plate[p_norm] = []
                violations_by_plate[p_norm].append(s)

        summary_list = []
        for p_norm, records in violations_by_plate.items():
            # Sort records chronologically
            records.sort(key=lambda x: x.get("timestamp", ""))
            latest_record = records[-1]
            first_record = records[0]
            for record in records:
                for field in ("decision_rules", "risk_factors"):
                    try:
                        record[field] = json.loads(record.get(field, "") or "[]")
                    except (TypeError, json.JSONDecodeError):
                        record[field] = []
                try:
                    record["risk_score"] = int(record.get("risk_score") or 0)
                    record["violation_count"] = int(record.get("violation_count") or 0)
                except (TypeError, ValueError):
                    record["risk_score"] = 0
                    record["violation_count"] = 0

            approved = approved_map.get(p_norm, {})
            plate_number = approved.get("plate_number") or latest_record.get("plate_number") or p_norm
            vehicle_id = approved.get("vehicle_id") or latest_record.get("vehicle_id") or "N/A"
            department = approved.get("department") or latest_record.get("department") or "Government Fleet"
            officer_name = approved.get("officer_name", "")
            officer_phone = approved.get("officer_phone", "")
            officer_email = approved.get("officer_email", "")

            v_count = len(records)

            # Determine Tier & Challan Status
            # 1, 2, 3 = Warning; 4+ = Challan
            if v_count == 1:
                tier = "WARNING_1"
                stage_label = "Warning #1"
                stage_type = "warning"
                fine_amount = 0
            elif v_count == 2:
                tier = "WARNING_2"
                stage_label = "Warning #2"
                stage_type = "warning"
                fine_amount = 0
            elif v_count == 3:
                tier = "WARNING_3"
                stage_label = "Warning #3 (Final Warning)"
                stage_type = "warning"
                fine_amount = 0
            else:
                tier = "CHALLAN_ELIGIBLE"
                stage_label = "Challan review required"
                stage_type = "challan"
                # PKR 2,500 base + PKR 1,000 for each violation above 4
                fine_amount = 2500 + (v_count - 4) * 1000

            safe_plate_id = "".join(c for c in plate_number.upper() if c.isalnum())
            issued = self.issued_challan_data(plate_number)
            challan_id = issued["challan_id"] if issued else None

            summary_item = {
                "plate_number": plate_number,
                "normalized_plate": normalize_plate(plate_number),
                "database_vehicle_id": latest_record.get("_vehicle_database_id"),
                "issued_challan_case_id": issued["case_id"] if issued else None,
                "vehicle_id": vehicle_id,
                "department": department,
                "officer_name": officer_name,
                "officer_phone": officer_phone,
                "officer_email": officer_email,
                "duty_schedule": approved.get("duty_schedule") or latest_record.get("duty_schedule", "24/7"),
                "authorized_areas": approved.get("authorized_areas") or latest_record.get("authorized_areas", ""),
                "total_violations": v_count,
                "tier": tier,
                "stage_label": stage_label,
                "stage_type": stage_type,
                "fine_amount": fine_amount,
                "challan_id": challan_id,
                "first_violation_date": first_record.get("timestamp", ""),
                "last_violation_date": latest_record.get("timestamp", ""),
                "latest_camera_area": latest_record.get("camera_area", ""),
                "latest_criteria": latest_record.get("violation_criteria", "UNAUTHORIZED_AREA"),
                "risk_score": latest_record.get("risk_score", 0),
                "risk_level": latest_record.get("risk_level", "NOT_ASSESSED"),
                "risk_factors": latest_record.get("risk_factors", []),
                **{key: latest_record[key] for key in ("risk_policy_version", "notification_priority", "escalation_role", "recommended_action", "risk_missing_context") if key in latest_record},
                "decision_reason": latest_record.get("decision_reason", ""),
                "decision_rules": latest_record.get("decision_rules", []),
                "latest_image": latest_record.get("image", ""),
                "violations_history": records,
            }

            # Filter by stage
            if stage:
                st = stage.strip().upper()
                if st == "WARNING" and stage_type != "warning":
                    continue
                if st == "CHALLAN" and stage_type != "challan":
                    continue

            # Filter by search query
            if query:
                q = query.strip().lower()
                matches = (
                    q in plate_number.lower()
                    or q in vehicle_id.lower()
                    or q in department.lower()
                    or q in officer_name.lower()
                    or q in officer_phone.lower()
                    or q in officer_email.lower()
                )
                if not matches:
                    continue

            summary_list.append(summary_item)

        # Sort by latest violation date descending
        summary_list.sort(key=lambda x: x.get("last_violation_date", ""), reverse=True)
        return summary_list

    def get_vehicle_challan_data(self, plate_number: str) -> dict | None:
        """Fetch complete challan particulars for a vehicle."""
        summaries = self.get_violations_summary()
        target = normalize_plate(plate_number)
        for item in summaries:
            if item["normalized_plate"] == target:
                return item
        return None

    def get_system_stats(self) -> dict:
        with self._lock:
            approved_count = 0
            departments = set()
            with self._lock:
                src = self._rows("approved_vehicles_path")
                for r in src:
                    approved_count += 1
                    if r.get("department"):
                        departments.add(r.get("department").strip())

            sightings = []
            with self._lock:
                src = self._rows("government_sightings_path")
                sightings = list(src)

            total_sightings = len(sightings)
            violations = sum(1 for s in sightings if s.get("status") == "VIOLATION")
            lawful = sum(1 for s in sightings if s.get("status") == "LAWFUL")
            unique_spotted_plates = len({normalize_plate(s.get("plate_number", "")) for s in sightings if s.get("plate_number")})

            # General detections count
            general_detections_count = 0
            with self._lock:
                src = self._rows("csv_path")
                general_detections_count = sum(1 for _ in src)

        # Violation summary metrics
        v_summaries = self.get_violations_summary()
        warnings_count = sum(1 for v in v_summaries if v["stage_type"] == "warning")
        eligible_count = sum(1 for v in v_summaries if v["stage_type"] == "challan")
        with self._lock as session:
            issued_filter = Challan.status.in_(["ISSUED", "UPHELD"])
            challans_count = session.scalar(select(func.count(func.distinct(Challan.vehicle_id))).where(issued_filter)) or 0
            total_fines = session.scalar(select(func.sum(Challan.fine_amount)).where(issued_filter)) or 0

        return {
            "authorized_vehicles_count": approved_count,
            "departments_count": len(departments),
            "total_government_sightings": total_sightings,
            "violations_count": violations,
            "lawful_count": lawful,
            "unique_spotted_plates": unique_spotted_plates,
            "general_detections_count": general_detections_count,
            "vehicles_with_warnings": warnings_count,
            "vehicles_with_challans": challans_count,
            "vehicles_challan_eligible": eligible_count,
            "total_fines_levied": total_fines,
        }


class LazyStore:
    """Defer connections until migrations have run and a request needs storage."""
    _instance = None

    def __getattr__(self, name):
        if self._instance is None:
            self._instance = DetectionStore()
        return getattr(self._instance, name)


store = LazyStore()
