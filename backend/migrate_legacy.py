"""One-time, transactional CSV/JSON import. Source files are never modified."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from .config import get_local_now, settings
from .db_models import ImportBatch, Detection, Evidence, Recognition, Sighting
from .db_records import timestamp

SOURCES = [
    ("approved_government_vehicles.csv", "approved_vehicles_path", "plate_number"),
    ("vehicle_detection_events.csv", "vehicle_events_path", "event_id"),
    ("plate_recognition_events.csv", "plate_recognition_path", "recognition_id"),
    ("detections.csv", "csv_path", None),
    ("government_vehicles_spotted.csv", "government_sightings_path", None),
    ("evidence_records.csv", "evidence_path", "evidence_id"),
    ("geofences.json", "geofences", "zone_id"),
]


def import_legacy(store, directory: Path, dry_run=False):
    report = []
    with store._lock as session:
        detection_keys = {tuple(r.payload.get(k, "") for k in ("timestamp", "plate_number", "image")): r.record_key
                          for r in session.scalars(select(Detection))}
        for filename, table, key_field in SOURCES:
            path = directory / filename
            if not path.exists():
                continue
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            previous = session.scalar(select(ImportBatch).where(ImportBatch.source == filename))
            if previous:
                report.append({"source": filename, "status": "already imported" if previous.checksum == checksum else "source changed; existing import retained",
                               "rows": previous.row_count})
                continue
            if filename.endswith(".json"):
                rows = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(rows, list):
                    raise ValueError(f"{filename}: expected an array")
            else:
                rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines(keepends=True)))
            keys = set()
            for index, original in enumerate(rows):
                row = dict(original)
                if None in row:
                    raise ValueError(f"{filename} row {index + 2}: unexpected CSV columns")
                if row.get("timestamp"):
                    timestamp(row["timestamp"])  # Fail before committing invalid capture times.
                if key_field:
                    key = row.get(key_field, "").strip()
                    if table == "approved_vehicles_path":
                        key = "".join(c for c in key.upper() if c.isalnum())
                    if not key or key in keys:
                        raise ValueError(f"{filename} row {index + 2}: missing or duplicate {key_field}")
                    keys.add(key)
                else:
                    row["_record_key"] = f"legacy-{table}-{index + 1}"
                signature = tuple(row.get(k, "") for k in ("timestamp", "plate_number", "image"))
                if table == "csv_path":
                    detection_keys[signature] = row["_record_key"]
                elif table == "government_sightings_path":
                    row["detection_key"] = detection_keys.get(signature, "")
                if not dry_run:
                    store._upsert(session, table, row)
            if not dry_run:
                session.add(ImportBatch(source=filename, checksum=checksum, row_count=len(rows), imported_at=get_local_now()))
            report.append({"source": filename, "status": "validated" if dry_run else "imported", "rows": len(rows)})
        if not dry_run:
            # Older detections did not store recognition IDs. Link through matching
            # sighting violation IDs when the original record contains that evidence.
            for sighting in session.scalars(select(Sighting)):
                if sighting.detection_id and (sighting.violation_id or "").startswith("VIOL-"):
                    recognition = session.scalar(select(Recognition).where(
                        Recognition.record_key == sighting.violation_id[5:]))
                    detection = session.get(Detection, sighting.detection_id)
                    if recognition and detection and detection.recognition_id is None:
                        already = session.scalar(select(Detection.id).where(Detection.recognition_id == recognition.id))
                        if already is None:
                            detection.recognition_id = recognition.id
            session.flush()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--directory", type=Path, default=settings.data_dir)
    args = parser.parse_args()
    from .storage import DetectionStore
    print(json.dumps(import_legacy(DetectionStore(), args.directory, args.dry_run), indent=2))
