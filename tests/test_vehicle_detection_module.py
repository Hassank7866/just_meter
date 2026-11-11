from db_support import make_test_engine
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from backend.compliance_engine import evaluate_compliance
from backend.config import settings
from backend.main import vehicle_for_plate
from backend.storage import DetectionStore


class VehicleDetectionModuleTests(unittest.TestCase):
    def setUp(self):
        self.previous_cooldown = settings.duplicate_cooldown_seconds
        object.__setattr__(settings, "duplicate_cooldown_seconds", 0)
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.original_paths = {
            "data_dir": settings.data_dir,
            "snapshots_dir": settings.snapshots_dir,
            "csv_path": settings.csv_path,
            "approved_vehicles_path": settings.approved_vehicles_path,
            "government_sightings_path": settings.government_sightings_path,
            "vehicle_events_path": settings.vehicle_events_path,
            "plate_recognition_path": settings.plate_recognition_path,
            "plate_crops_dir": settings.plate_crops_dir,
            "evidence_path": settings.evidence_path,
            "evidence_images_dir": settings.evidence_images_dir,
        }
        object.__setattr__(settings, "data_dir", root)
        object.__setattr__(settings, "snapshots_dir", root / "snapshots")
        object.__setattr__(settings, "csv_path", root / "detections.csv")
        object.__setattr__(settings, "approved_vehicles_path", root / "approved.csv")
        object.__setattr__(settings, "government_sightings_path", root / "government.csv")
        object.__setattr__(settings, "vehicle_events_path", root / "vehicle-events.csv")
        object.__setattr__(settings, "plate_recognition_path", root / "plate-recognitions.csv")
        object.__setattr__(settings, "plate_crops_dir", root / "snapshots" / "plates")
        object.__setattr__(settings, "evidence_path", root / "evidence.csv")
        object.__setattr__(settings, "evidence_images_dir", root / "snapshots" / "evidence")
        self.store = DetectionStore(make_test_engine())

    def tearDown(self):
        object.__setattr__(settings, "duplicate_cooldown_seconds", self.previous_cooldown)
        self.store.engine.dispose()
        for name, value in self.original_paths.items():
            object.__setattr__(settings, name, value)
        self.temp_dir.cleanup()

    def test_plate_is_associated_with_containing_vehicle(self):
        vehicles = [{"label": "car", "confidence": 0.9, "bbox": [0, 0, 200, 100]}]
        self.assertEqual(vehicle_for_plate(vehicles, [50, 40, 100, 70]), "car")
        self.assertIsNone(vehicle_for_plate(vehicles, [250, 40, 300, 70]))

    def test_frame_event_is_persisted_with_model_and_counts(self):
        vehicles = [
            {"label": "car", "confidence": 0.91, "bbox": [1, 2, 30, 40]},
            {"label": "bus", "confidence": 0.82, "bbox": [50, 5, 150, 100]},
        ]
        saved = self.store.save_vehicle_event(
            vehicles, "CAM-DEMO", "Mzd. Division", "RECORDED_VIDEO", 1280, 720, 45
        )
        self.assertTrue(saved["event_id"].startswith("DET-"))
        self.assertEqual(saved["vehicle_count"], 2)
        self.assertEqual(saved["model_version"], "YOLO11")

        history = self.store.latest_vehicle_events()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["camera_id"], "CAM-DEMO")
        self.assertEqual([dict(item, track_id=None) for item in vehicles],
                         [dict(item, track_id=None) for item in history[0]["detections"]])
        self.assertTrue(all(item["track_id"].startswith("TRK-") for item in history[0]["detections"]))
        self.assertEqual(json.loads(saved["detections_json"]), history[0]["detections"])

    def test_compliance_decision_and_repeat_risk_are_persisted(self):
        approved = {
            "plate_number": "AJK123", "vehicle_id": "GOV-001", "department": "Transport",
            "authorized_areas": "Mzd. Division", "duty_schedule": "24/7", "notes": "",
        }
        observed_at = datetime.fromisoformat("2026-10-03T20:00:00+05:00")
        frame = np.full((80, 160, 3), 120, dtype=np.uint8)

        for index in range(1, 3):
            compliance = evaluate_compliance(approved, "Poonch Division", observed_at)
            saved, reason = self.store.save(
                frame,
                {"plate_number": "AJK123", "confidence": 0.91, "bbox": [10, 10, 100, 50],
                 "recognition_id": f"ANPR-{index:03}"},
                None, None, None, "car", "Poonch Division", approved, compliance,
            )
            self.assertTrue(saved, reason)
            self.assertEqual(compliance["risk_score"], 35 + (index - 1) * 10)

        records = self.store.latest_government_sightings()
        self.assertEqual(records[0]["risk_level"], "MEDIUM")
        self.assertEqual(records[0]["violation_count"], "2")
        self.assertEqual(records[0]["violation_criteria"], "UNAUTHORIZED_AREA")
        self.assertEqual(json.loads(records[0]["decision_rules"])[0]["outcome"], "FAIL")
        self.assertIn("Prior violations in 30 days (1): +10", json.loads(records[0]["risk_factors"]))


if __name__ == "__main__":
    unittest.main()
