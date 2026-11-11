from db_support import make_test_engine
import tempfile
import unittest
from pathlib import Path

import numpy as np

from backend.anpr import analyze_plate_text, is_valid_plate, normalize_plate_text, suggest_plate_correction
from backend.config import settings
from backend.storage import DetectionStore


class AnprTextTests(unittest.TestCase):
    def test_normalization_and_format_validation(self):
        self.assertEqual(normalize_plate_text(" ajk- 123 "), "AJK123")
        self.assertTrue(is_valid_plate("AJK-123"))
        self.assertFalse(is_valid_plate("123-AJK"))

    def test_common_ocr_confusions_get_a_suggestion(self):
        self.assertEqual(suggest_plate_correction("AJK-12S"), "AJK125")
        result = analyze_plate_text("AJK-12S", 0.92, 0.70)
        self.assertEqual(result["suggested_text"], "AJK125")
        self.assertEqual(result["review_status"], "REVIEW_REQUIRED")

    def test_low_confidence_valid_plate_requires_review(self):
        result = analyze_plate_text("GB-103", 0.51, 0.70)
        self.assertTrue(result["valid_format"])
        self.assertEqual(result["review_status"], "REVIEW_REQUIRED")
        self.assertIn("LOW_CONFIDENCE", result["review_reason"])


class AnprStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        names = (
            "data_dir", "snapshots_dir", "csv_path", "approved_vehicles_path",
            "government_sightings_path", "vehicle_events_path", "plate_recognition_path",
            "plate_crops_dir",
            "evidence_path", "evidence_images_dir",
        )
        self.original = {name: getattr(settings, name) for name in names}
        replacements = {
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
        for name, value in replacements.items():
            object.__setattr__(settings, name, value)
        self.store = DetectionStore(make_test_engine())

    def tearDown(self):
        self.store.engine.dispose()
        for name, value in self.original.items():
            object.__setattr__(settings, name, value)
        self.temp_dir.cleanup()

    def test_crop_review_queue_and_manual_acceptance(self):
        frame = np.full((100, 200, 3), 255, dtype=np.uint8)
        plate = {"bbox": [20, 30, 120, 70], "confidence": 0.55, "plate_number": "AJK123"}
        analysis = analyze_plate_text("AJK123", 0.55, 0.70)
        saved = self.store.save_plate_recognition(
            frame, plate, analysis, "DET-001", "CAM-001", "Mzd. Division"
        )
        self.assertTrue((settings.snapshots_dir / saved["plate_crop"]).exists())
        self.assertEqual(len(self.store.get_plate_recognitions("REVIEW_REQUIRED")), 1)
        reviewed = self.store.review_plate_recognition(
            saved["recognition_id"], "AJK123", "ACCEPTED", "Officer One", "Verified visually"
        )
        self.assertEqual(reviewed["review_status"], "ACCEPTED")
        self.assertEqual(reviewed["final_text"], "AJK123")


if __name__ == "__main__":
    unittest.main()
