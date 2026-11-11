from db_support import make_test_engine
import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from backend.config import settings
from backend.storage import DetectionStore


class EvidenceModuleTests(unittest.TestCase):
    def setUp(self):
        self.previous_cooldown = settings.duplicate_cooldown_seconds
        object.__setattr__(settings, "duplicate_cooldown_seconds", 0)
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        names = (
            "data_dir", "snapshots_dir", "csv_path", "approved_vehicles_path",
            "government_sightings_path", "vehicle_events_path", "plate_recognition_path",
            "plate_crops_dir", "evidence_path", "evidence_images_dir",
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
        object.__setattr__(settings, "duplicate_cooldown_seconds", self.previous_cooldown)
        self.store.engine.dispose()
        for name, value in self.original.items():
            object.__setattr__(settings, name, value)
        self.temp_dir.cleanup()

    def create_evidence(self):
        frame = np.full((120, 240, 3), 180, dtype=np.uint8)
        crop_path = settings.plate_crops_dir / "ANPR-001.jpg"
        import cv2
        cv2.imwrite(str(crop_path), frame[40:80, 50:170])
        event = {
            "event_id": "DET-001", "timestamp": "2026-10-03T10:00:00+05:00",
            "camera_id": "CHECKPOINT-01", "camera_area": "Mzd. Division",
        }
        recognition = {
            "recognition_id": "ANPR-001", "timestamp": event["timestamp"],
            "normalized_text": "AJK123", "final_text": "AJK123", "plate_crop": "plates/ANPR-001.jpg",
        }
        plate = {"plate_number": "AJK123", "confidence": 0.91, "bbox": [50, 40, 170, 80]}
        return self.store.save_evidence(
            frame, event, recognition, plate, 34.3700, 73.4711, "car",
            {"department": "Transport"},
            {"status": "VIOLATION", "violation_id": "VIOL-ANPR-001"},
        )

    def test_evidence_hashes_verify_and_case_link_is_independent(self):
        evidence = self.create_evidence()
        self.assertTrue(evidence["evidence_id"].startswith("EVD-"))
        self.assertEqual(evidence["review_status"], "CAPTURED")
        self.assertEqual(evidence["case_status"], "ATTACHED_TO_VIOLATION")
        self.assertTrue(evidence["related_violation_id"].startswith("VIOL-"))
        self.assertEqual(len(evidence["full_image_sha256"]), 64)
        self.assertEqual(len(evidence["plate_crop_sha256"]), 64)
        result = self.store.verify_evidence(evidence["evidence_id"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["integrity_status"], "VERIFIED")
        unchanged = self.store.get_evidence(evidence["evidence_id"])
        self.assertEqual(unchanged["review_status"], "CAPTURED")

    def test_tampering_is_detected_and_review_is_persisted(self):
        evidence = self.create_evidence()
        full_path = settings.snapshots_dir / evidence["full_image"]
        full_path.write_bytes(b"tampered")
        result = self.store.verify_evidence(evidence["evidence_id"])
        self.assertFalse(result["valid"])
        after_verification = self.store.get_evidence(evidence["evidence_id"])
        self.assertEqual(after_verification["integrity_status"], "FAILED")
        self.assertEqual(after_verification["review_status"], "CAPTURED")
        reviewed = self.store.review_evidence(
            evidence["evidence_id"], "UNDER_REVIEW", "Auditor One", "Hash mismatch investigated",
        )
        self.assertEqual(reviewed["review_status"], "UNDER_REVIEW")
        self.assertEqual(reviewed["reviewer"], "Auditor One")
        self.assertEqual(reviewed["case_status"], "ATTACHED_TO_VIOLATION")
        completed = self.store.review_evidence(
            evidence["evidence_id"], "VERIFIED", "Auditor One", "Officer review complete",
        )
        self.assertEqual(completed["review_status"], "VERIFIED")
        self.assertEqual(completed["case_status"], "ATTACHED_TO_VIOLATION")

    def test_review_cannot_be_completed_before_review_starts(self):
        evidence = self.create_evidence()
        with self.assertRaisesRegex(ValueError, "must be UNDER_REVIEW"):
            self.store.review_evidence(
                evidence["evidence_id"], "VERIFIED", "Auditor One", "Review complete",
            )

    def test_legacy_status_is_migrated_into_independent_states(self):
        with (settings.data_dir / "evidence_records.csv").open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=[
                "evidence_id", "status", "related_violation_id", "related_challan_id",
            ])
            writer.writeheader()
            writer.writerow({
                "evidence_id": "EVD-LEGACY",
                "status": "ATTACHED_TO_VIOLATION",
                "related_violation_id": "VIOL-LEGACY",
            })

        from backend.migrate_legacy import import_legacy
        import_legacy(self.store, settings.data_dir)
        migrated_store = self.store
        migrated = migrated_store.get_evidence("EVD-LEGACY")
        self.assertEqual(migrated["review_status"], "CAPTURED")
        self.assertEqual(migrated["case_status"], "ATTACHED_TO_VIOLATION")
        self.assertEqual(migrated["related_violation_id"], "VIOL-LEGACY")

    def test_fourth_government_violation_creates_draft_without_premature_evidence_issuance(self):
        frame = np.full((120, 240, 3), 180, dtype=np.uint8)
        approved = {
            "plate_number": "AJK123", "vehicle_id": "GOV-001", "department": "Transport",
            "authorized_areas": "Mzd. Division", "duty_schedule": "24/7",
        }
        evidence_ids = []
        self.store._append("approved_vehicles_path", approved)
        for index in range(1, 5):
            recognition_id = f"ANPR-{index:03}"
            event_id = f"DET-{index:03}"
            saved, reason = self.store.save(
                frame,
                {
                    "plate_number": "AJK123", "confidence": 0.91, "bbox": [50, 40, 170, 80],
                    "recognition_id": recognition_id,
                },
                None, None, None, "car", "Mzd. Division", approved,
                {"status": "VIOLATION", "violation_criteria": "OUTSIDE_DUTY_HOURS"},
            )
            self.assertTrue(saved, reason)
            recognition = {
                "recognition_id": recognition_id,
                "timestamp": f"2026-10-03T10:0{index}:00+05:00",
                "normalized_text": "AJK123",
                "final_text": "AJK123",
                "plate_crop": "",
            }
            event = {
                "event_id": event_id, "timestamp": recognition["timestamp"],
                "camera_id": "CHECKPOINT-01", "camera_area": "Mzd. Division",
            }
            compliance = {
                "violation_id": f"VIOL-{recognition_id}",
                "status": "VIOLATION",
            }
            if index == 4:
                challan = self.store.get_vehicle_challan_data("AJK123")
                compliance["challan_id"] = challan["challan_id"]
            evidence = self.store.save_evidence(
                frame, event, recognition,
                {"plate_number": "AJK123", "confidence": 0.91, "bbox": [50, 40, 170, 80]},
                None, None, "car", approved, compliance,
            )
            evidence_ids.append(evidence["evidence_id"])

        records = [self.store.get_evidence(item) for item in evidence_ids]
        self.assertTrue(all(record["case_status"] == "ATTACHED_TO_VIOLATION" for record in records))
        self.assertTrue(all(not record["related_challan_id"] for record in records))
        self.assertTrue(all(record["related_violation_id"] for record in records))
        cases = self.store.list_challans()
        self.assertEqual(cases["total"], 1)
        self.assertEqual(cases["items"][0]["status"], "DRAFT")


if __name__ == "__main__":
    unittest.main()
