import csv
from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.config import settings
from backend.db_models import Detection, Evidence, ImportBatch, RiskAssessment, RiskPolicy, RiskTask, Sighting, Vehicle
from backend.migrate_legacy import import_legacy
from backend.risk_engine import RiskPolicyConfig, score_risk
from backend.storage import DetectionStore
from db_support import make_test_engine


class RiskEngineTests(unittest.TestCase):
    def score(self, criteria, **kwargs):
        return score_risk({"status": "VIOLATION", "violation_criteria": criteria}, RiskPolicyConfig().model_dump(), **kwargs)

    def test_overlapping_route_failures_count_once(self):
        result = self.score("UNAUTHORIZED_AREA|OUTSIDE_GEOFENCE|UNAUTHORIZED_AREA")
        self.assertEqual(result["risk_score"], 40)
        self.assertEqual(len(result["risk_breakdown"]), 1)

    def test_assignment_and_severe_history_are_explained_and_capped(self):
        result = self.score("OUTSIDE_GEOFENCE|OUTSIDE_DUTY_HOURS", prior_count=20,
                            prior_severe_count=20, assignment_context="CRITICAL")
        self.assertEqual(result["risk_score"], 100)
        self.assertEqual(result["risk_level"], "CRITICAL")
        self.assertEqual(result["notification_priority"], "URGENT")
        self.assertEqual(result["escalation_role"], "Supervisory Officer")
        self.assertEqual(result["recommended_action"], "CHALLAN_REVIEW")
        self.assertTrue(result["requires_officer_approval"])

    def test_integrity_minimum_and_missing_context(self):
        config = RiskPolicyConfig().model_dump()
        config["category_weights"]["PLATE_MISMATCH"] = 1
        result = score_risk({"status": "VIOLATION", "violation_criteria": "PLATE_MISMATCH"}, config)
        self.assertEqual(result["risk_level"], "CRITICAL")
        self.assertTrue(result["risk_missing_context"])

    def test_unknown_or_unconfirmed_criteria_cannot_be_scored_as_confirmed(self):
        self.assertEqual(self.score("NEW_RULE")["risk_level"], "PENDING_REVIEW")
        for status, level in [("LAWFUL", "NOT_APPLICABLE"), ("REVIEW_REQUIRED", "PENDING_REVIEW")]:
            result = score_risk({"status": status}, RiskPolicyConfig().model_dump(), prior_count=20)
            self.assertEqual((result["risk_score"], result["risk_level"]), (0, level))
            self.assertEqual(result["recommended_action"], "NONE")

    def test_policy_rejects_bad_thresholds_and_weights(self):
        with self.assertRaises(ValueError):
            RiskPolicyConfig(medium_threshold=90, high_threshold=50)
        with self.assertRaises(ValueError):
            RiskPolicyConfig(category_weights={"UNKNOWN": -1})


class DatabaseRiskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original = {name: getattr(settings, name) for name in (
            "snapshots_dir", "plate_crops_dir", "evidence_images_dir")}
        for name, child in [("snapshots_dir", "images"), ("plate_crops_dir", "images/plates"), ("evidence_images_dir", "images/evidence")]:
            object.__setattr__(settings, name, self.root / child)
        self.store = DetectionStore(make_test_engine())
        self.frame = np.zeros((80, 160, 3), dtype=np.uint8)
        self.vehicle = {"plate_number": "AJK123", "vehicle_id": "GOV-1", "department": "Transport",
                        "authorized_areas": "Mzd. Division", "duty_schedule": "24/7", "risk_context": "STANDARD"}
        self.store.add_approved_vehicle(self.vehicle)
        self.time = datetime.fromisoformat("2026-10-06T12:00:00+05:00")

    def tearDown(self):
        self.store.engine.dispose()
        for name, value in self.original.items():
            object.__setattr__(settings, name, value)
        self.temp.cleanup()

    def capture(self, key, when, criteria="UNAUTHORIZED_AREA"):
        compliance = {"status": "VIOLATION", "violation_criteria": criteria}
        saved, reason = self.store.save(self.frame, {"plate_number": "AJK123", "recognition_id": key,
            "confidence": 0.9, "bbox": [10, 10, 90, 40]}, None, None, None, "car", "Poonch Division",
            self.vehicle, compliance, when)
        return saved, reason, compliance

    def count(self, model):
        with self.store._lock as session:
            return session.scalar(select(func.count()).select_from(model))

    def test_window_excludes_old_and_future_events(self):
        self.capture("old", self.time - timedelta(days=31))
        self.capture("recent", self.time - timedelta(days=1))
        self.capture("future", self.time + timedelta(days=1))
        saved, _, result = self.capture("current", self.time)
        self.assertTrue(saved)
        self.assertEqual(result["risk_prior_count"], 1)
        self.assertEqual(result["risk_score"], 45)

    def test_restart_cooldown_and_recognition_idempotency(self):
        self.capture("first", self.time)
        self.store = DetectionStore(self.store.engine)
        self.assertFalse(self.capture("first", self.time + timedelta(hours=1))[0])
        self.assertFalse(self.capture("duplicate-frame", self.time + timedelta(seconds=2))[0])
        self.assertEqual(self.count(Detection), 1)
        self.assertEqual(self.count(RiskAssessment), 1)
        self.assertEqual(self.count(RiskTask), 1)

    def test_risk_failure_rolls_back_detection_sighting_and_task(self):
        with patch.object(self.store, "_persist_risk", side_effect=RuntimeError("storage failure")):
            with self.assertRaises(RuntimeError):
                self.capture("failed", self.time)
        self.assertEqual(self.count(Detection), 0)
        self.assertEqual(self.count(Sighting), 0)
        self.assertEqual(self.count(RiskTask), 0)

    def test_new_policy_preserves_old_assessment_and_checks_version(self):
        self.capture("first", self.time)
        old = self.store.get_risk_policy()
        old["config"]["category_weights"]["UNAUTHORIZED_AREA"] = 5
        new = self.store.update_risk_policy(old["config"], "admin", old["version"])
        self.assertEqual(new["version"], 2)
        with self.assertRaises(ValueError):
            self.store.update_risk_policy(old["config"], "admin", 1)
        _, _, result = self.capture("second", self.time + timedelta(days=40))
        self.assertEqual(result["risk_score"], 5)
        tasks = self.store.get_risk_tasks()
        self.assertEqual(sorted(t["risk_policy_version"] for t in tasks), [1, 2])
        self.assertEqual(sorted(t["risk_score"] for t in tasks), [5, 35])

    def test_task_role_and_acknowledgment(self):
        self.capture("high", self.time, "OUTSIDE_GEOFENCE|OUTSIDE_DUTY_HOURS")
        task = self.store.get_risk_tasks()[0]
        with self.assertRaises(PermissionError):
            self.store.acknowledge_risk_task(task["id"], "transport", "Transport Officer")
        result = self.store.acknowledge_risk_task(task["id"], "supervisor", "Supervisory Officer")
        self.assertEqual(result["status"], "ACKNOWLEDGED")
        self.assertEqual(self.store.get_risk_tasks(), [])

    def write_csv(self, filename, rows):
        with (self.root / filename).open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def test_import_preserves_links_files_and_is_repeatable(self):
        event = {"event_id": "DET-OLD", "timestamp": self.time.isoformat(), "camera_id": "CAM-OLD", "vehicle_count": "1"}
        recognition = {"recognition_id": "ANPR-OLD", "detection_event_id": "DET-OLD", "timestamp": self.time.isoformat(),
                       "normalized_text": "AJK123", "confidence": "0.9", "review_status": "ACCEPTED"}
        detection = {"timestamp": self.time.isoformat(), "plate_number": "AJK123", "image": "original.jpg"}
        sighting = detection | {"status": "VIOLATION", "violation_id": "VIOL-ANPR-OLD", "risk_score": "35", "risk_level": "MEDIUM"}
        evidence = {"evidence_id": "EVD-OLD", "detection_event_id": "DET-OLD", "recognition_id": "ANPR-OLD",
                    "related_violation_id": "VIOL-ANPR-OLD", "full_image": "evidence/original.jpg", "full_image_sha256": "abc"}
        for name, row in [("vehicle_detection_events.csv", event), ("plate_recognition_events.csv", recognition),
                          ("detections.csv", detection), ("government_vehicles_spotted.csv", sighting), ("evidence_records.csv", evidence)]:
            self.write_csv(name, [row])
        before = {p.name: p.read_bytes() for p in self.root.glob("*.csv")}
        import_legacy(self.store, self.root)
        import_legacy(self.store, self.root)
        self.assertEqual(self.count(Detection), 1)
        self.assertEqual(self.count(ImportBatch), 5)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.glob("*.csv")})
        with self.store._lock as session:
            item = session.scalar(select(Evidence))
            self.assertIsNotNone(item.event_id)
            self.assertIsNotNone(item.recognition_id)
            self.assertIsNotNone(item.sighting_id)
            self.assertEqual(item.full_image, "evidence/original.jpg")
            self.assertIsNotNone(session.scalar(select(Detection)).recognition_id)

    def test_invalid_import_rolls_back_entire_batch_and_dry_run_writes_nothing(self):
        self.write_csv("vehicle_detection_events.csv", [{"event_id": "DET-1", "vehicle_count": "1", "timestamp": self.time.isoformat()}])
        report = import_legacy(self.store, self.root, dry_run=True)
        self.assertEqual(report[0]["status"], "validated")
        self.assertEqual(self.count(ImportBatch), 0)
        self.write_csv("plate_recognition_events.csv", [{"recognition_id": "", "timestamp": self.time.isoformat()}])
        with self.assertRaises(ValueError):
            import_legacy(self.store, self.root)
        self.assertEqual(self.count(ImportBatch), 0)
        from backend.db_models import VehicleEvent
        self.assertEqual(self.count(VehicleEvent), 0)

    def test_registry_delete_preserves_historical_foreign_key(self):
        self.capture("first", self.time)
        self.store.delete_approved_vehicle("AJK123")
        self.assertIsNone(self.store.find_approved_vehicle("AJK123"))
        with self.store._lock as session:
            sighting = session.scalar(select(Sighting))
            vehicle = session.get(Vehicle, sighting.vehicle_id)
            self.assertFalse(vehicle.active)

    def test_plate_correction_preserves_vehicle_identity_and_risk_history(self):
        self.capture("first", self.time)
        with self.store._lock as session:
            original_id = session.scalar(select(Vehicle.id))
        success, reason = self.store.update_approved_vehicle("AJK123", {"plate_number": "AJK124"})
        self.assertTrue(success, reason)
        with self.store._lock as session:
            vehicle = session.scalar(select(Vehicle))
            self.assertEqual(vehicle.id, original_id)
            self.assertEqual(vehicle.normalized_plate, "AJK124")
            policy, risk = self.store._score_current_risk(session,
                {"status": "VIOLATION", "violation_criteria": "UNAUTHORIZED_AREA"},
                "AJK124", self.time + timedelta(days=1), vehicle.payload)
            self.assertEqual(risk["risk_prior_count"], 1)
