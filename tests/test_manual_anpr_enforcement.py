from db_support import make_test_engine
import asyncio
import tempfile
import unittest
from pathlib import Path

import numpy as np

from backend import main
from backend.anpr import analyze_plate_text
from backend.config import settings
from backend.models import PlateReviewRequest
from backend.storage import DetectionStore


class ManualAnprEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        path_values = {
            "data_dir": root,
            "snapshots_dir": root / "snapshots",
            "csv_path": root / "detections.csv",
            "approved_vehicles_path": root / "approved.csv",
            "government_sightings_path": root / "government.csv",
            "vehicle_events_path": root / "vehicle-events.csv",
            "plate_recognition_path": root / "plate-recognitions.csv",
            "plate_crops_dir": root / "snapshots" / "plates",
            "evidence_path": root / "evidence.csv",
            "evidence_images_dir": root / "snapshots" / "evidence",
        }
        self.original_paths = {name: getattr(settings, name) for name in path_values}
        for name, value in path_values.items():
            object.__setattr__(settings, name, value)
        self.original_store = main.store
        self.store = DetectionStore(make_test_engine())
        main.store = self.store

    def tearDown(self):
        self.store.engine.dispose()
        main.store = self.original_store
        for name, value in self.original_paths.items():
            object.__setattr__(settings, name, value)
        self.temp_dir.cleanup()

    def test_manually_accepted_plate_runs_compliance_and_updates_evidence(self):
        frame = np.full((100, 200, 3), 160, dtype=np.uint8)
        plate = {"plate_number": "AJK12S", "raw_text": "AJK12S", "confidence": 0.55,
                 "bbox": [30, 35, 150, 65]}
        analysis = analyze_plate_text("AJK12S", 0.55, 0.70)
        event = self.store.save_vehicle_event(
            [], "CAM-REVIEW", "Poonch Division", "LIVE_FRAME", 200, 100,
        )
        recognition = self.store.save_plate_recognition(
            frame, plate, analysis, event["event_id"], event["camera_id"], event["camera_area"],
        )
        evidence = self.store.save_evidence(
            frame, event, recognition, plate, 33.9, 73.8, "car", None, None,
        )
        self.store.add_approved_vehicle({
            "plate_number": "AJK123", "vehicle_id": "GOV-123", "department": "Transport",
            "authorized_areas": "Mzd. Division", "duty_schedule": "24/7",
        })

        response = asyncio.run(main.review_plate_recognition(
            recognition["recognition_id"],
            PlateReviewRequest(
                corrected_text="AJK123", status="ACCEPTED", reviewer="Officer One",
                notes="Plate visually confirmed",
            ),
        ))

        enforcement = response["enforcement"]
        self.assertEqual(response["recognition"]["review_status"], "ACCEPTED")
        self.assertEqual(enforcement["compliance"]["status"], "VIOLATION")
        self.assertEqual(enforcement["compliance"]["risk_score"], 35)
        self.assertTrue(enforcement["saved"])

        sightings = self.store.latest_government_sightings()
        self.assertEqual(len(sightings), 1)
        self.assertEqual(sightings[0]["plate_number"], "AJK123")
        self.assertEqual(sightings[0]["risk_level"], "MEDIUM")

        reviewed_evidence = self.store.get_evidence(evidence["evidence_id"])
        self.assertEqual(reviewed_evidence["plate_number"], "AJK123")
        self.assertEqual(reviewed_evidence["related_violation_id"], f"VIOL-{recognition['recognition_id']}")
        self.assertEqual(reviewed_evidence["case_status"], "ATTACHED_TO_VIOLATION")


if __name__ == "__main__":
    unittest.main()
