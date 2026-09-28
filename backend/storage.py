from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from .config import get_local_now, settings

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
]
GOVERNMENT_HEADERS = HEADERS + [
    "vehicle_id",
    "department",
    "authorized_areas",
    "duty_schedule",
    "status",
    "violation_criteria",
    "notes",
]


def normalize_plate(plate: str) -> str:
    """Match plates regardless of spaces, hyphens, punctuation, or letter case."""
    return "".join(char for char in plate.upper() if char.isalnum())


class DetectionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._last_seen: dict[str, datetime] = {}
        settings.snapshots_dir.mkdir(parents=True, exist_ok=True)
        if not settings.csv_path.exists():
            with settings.csv_path.open("w", newline="", encoding="utf-8") as output:
                csv.DictWriter(output, fieldnames=HEADERS).writeheader()
        if not settings.approved_vehicles_path.exists():
            with settings.approved_vehicles_path.open("w", newline="", encoding="utf-8") as output:
                csv.DictWriter(output, fieldnames=APPROVED_HEADERS).writeheader()
        if not settings.government_sightings_path.exists():
            with settings.government_sightings_path.open("w", newline="", encoding="utf-8") as output:
                csv.DictWriter(output, fieldnames=GOVERNMENT_HEADERS).writeheader()

    def is_duplicate(self, plate: str, now: datetime) -> bool:
        previous = self._last_seen.get(plate)
        return previous is not None and (now - previous).total_seconds() < settings.duplicate_cooldown_seconds

    def find_approved_vehicle(self, plate_number: str) -> dict[str, str] | None:
        target = normalize_plate(plate_number)
        if not target:
            return None
        with self._lock, settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                if normalize_plate(row.get("plate_number", "")) == target:
                    return {key: row.get(key, "") for key in APPROVED_HEADERS}
        return None

    def save(self, frame: np.ndarray, plate: dict, latitude: float | None, longitude: float | None,
             accuracy: float | None, vehicle_type: str | None, camera_area: str,
             approved_vehicle: dict[str, str] | None = None,
             compliance: dict[str, str] | None = None) -> tuple[bool, str | None]:
        now = get_local_now()
        with self._lock:
            if self.is_duplicate(plate["plate_number"], now):
                return False, "duplicate within cooldown"
            safe_plate = "".join(ch for ch in plate["plate_number"] if ch.isalnum() or ch in "-_")[:32] or "unknown"
            filename = f"{safe_plate}_{now.strftime('%Y%m%dT%H%M%S_%f')}.jpg"
            snapshot_path = settings.snapshots_dir / filename
            if not cv2.imwrite(str(snapshot_path), frame):
                raise RuntimeError("Could not write snapshot")
            row = {
                "timestamp": now.isoformat(), "plate_number": plate["plate_number"],
                "camera_area": camera_area,
                "confidence": plate["confidence"], "latitude": latitude, "longitude": longitude,
                "location_accuracy_m": accuracy, "vehicle_type": vehicle_type or "",
                "image": filename, "bbox": ",".join(map(str, plate["bbox"])),
            }
            with settings.csv_path.open("a", newline="", encoding="utf-8") as output:
                csv.DictWriter(output, fieldnames=HEADERS).writerow(row)
            if approved_vehicle:
                government_row = row | {
                    "vehicle_id": approved_vehicle.get("vehicle_id", ""),
                    "department": approved_vehicle.get("department", ""),
                    "authorized_areas": approved_vehicle.get("authorized_areas", ""),
                    "duty_schedule": approved_vehicle.get("duty_schedule", ""),
                    "status": compliance["status"] if compliance else "UNASSESSED",
                    "violation_criteria": compliance["violation_criteria"] if compliance else "",
                    "notes": approved_vehicle.get("notes", ""),
                }
                with settings.government_sightings_path.open("a", newline="", encoding="utf-8") as output:
                    csv.DictWriter(output, fieldnames=GOVERNMENT_HEADERS).writerow(government_row)
            self._last_seen[plate["plate_number"]] = now
        return True, None

    def latest(self, limit: int) -> list[dict]:
        with self._lock, settings.csv_path.open(newline="", encoding="utf-8-sig") as source:
            rows = list(csv.DictReader(source))
        return list(reversed(rows[-limit:]))

    def latest_government_sightings(self, limit: int = 1000) -> list[dict]:
        with self._lock, settings.government_sightings_path.open(newline="", encoding="utf-8-sig") as source:
            rows = list(csv.DictReader(source))
        return list(reversed(rows[-limit:]))

    def get_all_approved_vehicles(self, query: str | None = None, area: str | None = None) -> list[dict]:
        with self._lock, settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as source:
            rows = list(csv.DictReader(source))

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

        with self._lock:
            rows = []
            if settings.approved_vehicles_path.exists():
                with settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as source:
                    rows = list(csv.DictReader(source))

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
            }
            rows.append(new_row)

            with settings.approved_vehicles_path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=APPROVED_HEADERS)
                writer.writeheader()
                writer.writerows(rows)

        return True, None

    def update_approved_vehicle(self, original_plate: str, updated_record: dict) -> tuple[bool, str | None]:
        target = normalize_plate(original_plate)
        if not target:
            return False, "Invalid target plate number"

        new_plate = updated_record.get("plate_number", "").strip() or original_plate
        new_target = normalize_plate(new_plate)

        with self._lock:
            rows = []
            if settings.approved_vehicles_path.exists():
                with settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as source:
                    rows = list(csv.DictReader(source))

            # Check if new_plate conflicts with another entry
            if new_target != target:
                for r in rows:
                    if normalize_plate(r.get("plate_number", "")) == new_target:
                        return False, f"Another vehicle already exists with plate '{new_plate}'"

            found = False
            for idx, r in enumerate(rows):
                if normalize_plate(r.get("plate_number", "")) == target:
                    rows[idx] = {
                        "plate_number": new_plate,
                        "vehicle_id": updated_record.get("vehicle_id", r.get("vehicle_id", "")).strip(),
                        "department": updated_record.get("department", r.get("department", "")).strip(),
                        "authorized_areas": updated_record.get("authorized_areas", r.get("authorized_areas", "")).strip(),
                        "duty_schedule": updated_record.get("duty_schedule", r.get("duty_schedule", "")).strip() or "24/7",
                        "notes": updated_record.get("notes", r.get("notes", "")).strip(),
                        "officer_name": updated_record.get("officer_name", r.get("officer_name", "")).strip(),
                        "officer_phone": updated_record.get("officer_phone", r.get("officer_phone", "")).strip(),
                        "officer_email": updated_record.get("officer_email", r.get("officer_email", "")).strip(),
                    }
                    found = True
                    break

            if not found:
                return False, f"Vehicle with plate '{original_plate}' not found in registry"

            with settings.approved_vehicles_path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=APPROVED_HEADERS)
                writer.writeheader()
                writer.writerows(rows)

        return True, None

    def delete_approved_vehicle(self, plate_number: str) -> tuple[bool, str | None]:
        target = normalize_plate(plate_number)
        if not target:
            return False, "Invalid plate number"

        with self._lock:
            rows = []
            if settings.approved_vehicles_path.exists():
                with settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as source:
                    rows = list(csv.DictReader(source))

            filtered = [r for r in rows if normalize_plate(r.get("plate_number", "")) != target]
            if len(filtered) == len(rows):
                return False, f"Vehicle with plate '{plate_number}' not found"

            with settings.approved_vehicles_path.open("w", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=APPROVED_HEADERS)
                writer.writeheader()
                writer.writerows(filtered)

        return True, None

    def get_violations_summary(self, query: str | None = None, stage: str | None = None) -> list[dict]:
        """Aggregate all violations grouped by vehicle plate, computing warning/challan escalation status."""
        with self._lock:
            sightings = []
            if settings.government_sightings_path.exists():
                with settings.government_sightings_path.open(newline="", encoding="utf-8-sig") as src:
                    sightings = list(csv.DictReader(src))

            approved_map: dict[str, dict] = {}
            if settings.approved_vehicles_path.exists():
                with settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as src:
                    for r in csv.DictReader(src):
                        norm = normalize_plate(r.get("plate_number", ""))
                        if norm:
                            approved_map[norm] = {k: r.get(k, "") for k in APPROVED_HEADERS}

        # Filter violations only
        violations_by_plate: dict[str, list[dict]] = {}
        for s in sightings:
            if s.get("status") == "VIOLATION":
                p_norm = normalize_plate(s.get("plate_number", ""))
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
                tier = "CHALLAN_ISSUED"
                stage_label = "Challan Issued"
                stage_type = "challan"
                # PKR 2,500 base + PKR 1,000 for each violation above 4
                fine_amount = 2500 + (v_count - 4) * 1000

            safe_plate_id = "".join(c for c in plate_number.upper() if c.isalnum())
            challan_id = f"CHL-2026-{safe_plate_id}-{v_count:02d}" if v_count >= 4 else None

            summary_item = {
                "plate_number": plate_number,
                "normalized_plate": p_norm,
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
            if settings.approved_vehicles_path.exists():
                with settings.approved_vehicles_path.open(newline="", encoding="utf-8-sig") as src:
                    for r in csv.DictReader(src):
                        approved_count += 1
                        if r.get("department"):
                            departments.add(r.get("department").strip())

            sightings = []
            if settings.government_sightings_path.exists():
                with settings.government_sightings_path.open(newline="", encoding="utf-8-sig") as src:
                    sightings = list(csv.DictReader(src))

            total_sightings = len(sightings)
            violations = sum(1 for s in sightings if s.get("status") == "VIOLATION")
            lawful = sum(1 for s in sightings if s.get("status") == "LAWFUL")
            unique_spotted_plates = len({normalize_plate(s.get("plate_number", "")) for s in sightings if s.get("plate_number")})

            # General detections count
            general_detections_count = 0
            if settings.csv_path.exists():
                with settings.csv_path.open(newline="", encoding="utf-8-sig") as src:
                    general_detections_count = sum(1 for _ in csv.DictReader(src))

        # Violation summary metrics
        v_summaries = self.get_violations_summary()
        warnings_count = sum(1 for v in v_summaries if v["stage_type"] == "warning")
        challans_count = sum(1 for v in v_summaries if v["stage_type"] == "challan")
        total_fines = sum(v.get("fine_amount", 0) for v in v_summaries)

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
            "total_fines_levied": total_fines,
        }


store = DetectionStore()

