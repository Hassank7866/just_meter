"""Vehicle identity, source-time semantics, linked history and API boundaries."""
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import select

from backend import main
from backend.auth import create_access_token
from backend.db_models import (Department, Detection, DutyReview, Evidence, Recognition,
                               RiskAssessment, RiskPolicy, RiskTask, Sighting, Vehicle)
from backend.storage import DetectionStore
from backend.vims_schema import VimsBatch
from db_support import make_test_engine, authenticated_headers


def at(day=7, hour=8):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def seed(store):
    data = json.loads((Path(__file__).parents[1] / "backend/fixtures/vims_sample.json").read_text())
    store.vims_sync(VimsBatch.model_validate(data), "admin@test", expected_revision=0)
    return data, store.twin_vehicle_id("sample-001")


def sighting(store, vehicle_id, key="capture-1", status="VIOLATION", day=7):
    with store._lock as session:
        row = Sighting(record_key=key, vehicle_id=vehicle_id, observed_at=at(day), normalized_plate="SAMPLE001",
            status=status, payload={"_record_key": key, "plate_number": "SAMPLE001", "department": "Capture department",
                                   "timestamp": at(day).isoformat(), "status": status, "camera_area": "Mzd. Division"})
        session.add(row)
        session.flush()
        return row.id


class DigitalTwinTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())
        self.data, self.vehicle_id = seed(self.store)

    def tearDown(self):
        self.store.engine.dispose()

    def profile(self, **kwargs):
        return self.store.vehicle_digital_twin(self.vehicle_id, **kwargs)

    def test_empty_history_and_unconfirmed_source_do_not_claim_authorization(self):
        result = self.profile(as_of=at())
        self.assertEqual(result["compliance"]["total_sightings"], 0)
        self.assertIsNone(result["risk"])
        self.assertIsNone(result["latest_sighting"])
        self.assertEqual(result["open_tasks"], 0)
        self.assertEqual(result["duty_verification"]["status"], "REVIEW")
        self.assertEqual(len(result["source_context"]["assignments"]), 1)
        self.assertEqual(len(result["source_context"]["duty_slips"]), 1)
        self.assertEqual(result["timeline"]["total"], 2)

    def test_no_vims_source_and_missing_vehicle(self):
        with self.store._lock as session:
            vehicle = session.get(Vehicle, self.vehicle_id)
            vehicle.vims_source_id = vehicle.vims_external_id = None
        result = self.profile()
        self.assertIsNone(result["source_context"]["source"])
        self.assertEqual(result["duty_verification"]["status"], "REVIEW")
        self.assertTrue(result["warnings"])
        self.assertIsNone(self.store.vehicle_digital_twin(99999))

    def test_future_exports_and_end_exclusive_periods(self):
        before = self.profile(as_of=at(hour=3))
        self.assertIsNone(before["source_context"]["vehicle"])
        self.assertEqual(before["source_context"]["assignments"], [])
        # The example slip ends at noon UTC (17:00 Pakistan).
        self.assertEqual(self.profile(as_of=at(hour=12))["source_context"]["duty_slips"], [])

    def test_plate_change_transfer_archive_preserve_history_and_historical_source(self):
        observation = sighting(self.store, self.vehicle_id)
        self.data["batch_id"] = "next"
        self.data["exported_at"] = at(8).isoformat()
        self.data["vehicles"][0]["plate_number"] = "NEW002"
        self.data["vehicles"][0]["active"] = False
        self.data["assignments"][0]["status"] = "CANCELLED"
        self.data["duty_slips"][0]["status"] = "CANCELLED"
        self.data["departments"][0]["name"] = "New department name"
        self.store.vims_sync(VimsBatch.model_validate(self.data), "admin@test", expected_revision=1)
        result = self.profile(as_of=at())
        self.assertEqual(result["vehicle"]["plate_number"], "NEW002")
        self.assertFalse(result["vehicle"]["active"])
        self.assertEqual(result["vehicle"]["department"], "New department name")
        self.assertEqual(result["source_context"]["vehicle"]["plate_number"], "SAMPLE001")
        self.assertEqual(result["source_context"]["assignments"][0]["department"]["name"], "Example Transport Department")
        self.assertEqual(result["latest_sighting"]["id"], observation)
        self.assertEqual(result["latest_sighting"]["department"], "Capture department")
        self.assertEqual(result["compliance"]["total_violations"], 1)
        self.assertEqual(self.store.twin_reference_id(sighting_key="capture-1"), self.vehicle_id)
        self.assertEqual(self.store.twin_vehicle_id("new-002"), self.vehicle_id)
        self.assertIsNone(self.store.twin_vehicle_id("sample001"))
        self.assertEqual(self.store.twin_vehicles()["items"][0]["active"], False)

    def test_timeline_pagination_filters_and_totals_are_independent(self):
        sighting(self.store, self.vehicle_id, "one", day=7)
        sighting(self.store, self.vehicle_id, "two", "LAWFUL", day=8)
        sighting(self.store, self.vehicle_id, "three", "REVIEW_REQUIRED", day=8)
        first = self.profile(start=at(8), end=at(8), limit=1)
        second = self.profile(start=at(8), end=at(8), limit=1, offset=1)
        self.assertEqual(first["timeline"]["total"], 2)
        self.assertNotEqual(first["timeline"]["items"][0]["id"], second["timeline"]["items"][0]["id"])
        self.assertEqual(first["compliance"]["total_sightings"], 3)
        self.assertEqual(first["compliance"]["total_violations"], 1)
        self.assertEqual(self.profile(start=at(9))["timeline"]["items"], [])

    def test_other_vehicle_history_is_never_attached_by_plate_text(self):
        with self.store._lock as session:
            other = Vehicle(record_key="OTHER", normalized_plate="OTHER", plate_number="OTHER",
                            vehicle_id="OTHER", payload={})
            session.add(other)
            session.flush()
            other_id = other.id
        sighting(self.store, other_id)  # Deliberately has the same captured plate text.
        self.assertEqual(self.profile()["compliance"]["total_sightings"], 0)
        self.assertIsNone(self.profile()["latest_sighting"])

    def test_risk_tasks_reviews_and_both_evidence_link_paths(self):
        sid = sighting(self.store, self.vehicle_id)
        with self.store._lock as session:
            policy = RiskPolicy(version=1, created_at=at(), created_by="admin@test", config={})
            recognition = Recognition(record_key="rec", observed_at=at(), plate_number="SAMPLE001",
                                      confidence=0.9, review_status="ACCEPTED", payload={})
            session.add_all([policy, recognition])
            session.flush()
            detection = Detection(record_key="det", recognition_id=recognition.id, observed_at=at(),
                                  normalized_plate="SAMPLE001", payload={})
            assessment = RiskAssessment(sighting_id=sid, policy_id=policy.id, assessed_at=at(),
                                        score=75, level="HIGH", result={"risk_factors": ["Repeat misuse"]})
            session.add_all([detection, assessment])
            session.flush()
            session.get(Sighting, sid).detection_id = detection.id
            session.add(RiskTask(assessment_id=assessment.id, priority="HIGH", assigned_role="Supervisory Officer",
                                 recommended_action="REVIEW", status="OPEN"))
            session.add(DutyReview(sighting_id=sid, reviewed_at=at(), reviewed_by="officer@test", notes="Checked records",
                                   original={"status": "REVIEW_REQUIRED"}, decision={"status": "VIOLATION"}))
            for key, direct in (("evd-direct", True), ("evd-rec", False)):
                session.add(Evidence(record_key=key, sighting_id=sid if direct else None,
                    recognition_id=recognition.id, review_status="CAPTURED", case_status="UNASSIGNED",
                    full_image="evidence/test.jpg", full_image_sha256="a" * 64,
                    payload={"evidence_id": key, "full_image": "evidence/test.jpg"}))
            # Unlinked evidence with the same plate is intentionally excluded.
            session.add(Evidence(record_key="unlinked", review_status="CAPTURED", case_status="UNASSIGNED",
                full_image="none.jpg", full_image_sha256="b" * 64, payload={"plate_number": "SAMPLE001"}))
        result = self.profile()
        self.assertEqual(result["risk"]["score"], 75)
        self.assertEqual(result["open_tasks"], 1)
        events = result["timeline"]["items"]
        self.assertEqual(len([e for e in events if e["kind"] == "evidence"]), 2)
        self.assertEqual(next(e for e in events if e["kind"] == "risk")["data"]["task"]["status"], "OPEN")
        self.assertEqual(next(e for e in events if e["kind"] == "duty_review")["data"]["original"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(self.store.twin_reference_id(evidence_key="evd-direct"), self.vehicle_id)
        self.assertEqual(self.store.twin_reference_id(evidence_key="evd-rec"), self.vehicle_id)
        self.assertIsNone(self.store.twin_reference_id(evidence_key="unlinked"))

    def test_live_read_model_reflects_new_observations(self):
        self.assertEqual(self.profile()["compliance"]["total_sightings"], 0)
        sighting(self.store, self.vehicle_id)
        self.assertEqual(self.profile()["compliance"]["total_sightings"], 1)
        with self.store._lock as session:
            session.scalar(select(Sighting)).status = "LAWFUL"
        self.assertEqual(self.profile()["compliance"]["total_violations"], 0)


class DigitalTwinApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        _, self.vehicle_id = seed(self.store)
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    def headers(self, role="Administrator"):
        return authenticated_headers(self.store, role)

    async def test_authenticated_read_access_and_reference_resolution(self):
        path = f"/api/vehicles/{self.vehicle_id}/digital-twin"
        self.assertEqual((await self.client.get(path)).status_code, 401)
        self.assertEqual((await self.client.get(path, headers=self.headers("Auditor"))).status_code, 403)
        for role in ("Administrator", "Transport Officer", "Supervisory Officer"):
            response = await self.client.get(path, headers=self.headers(role))
            self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.get("/api/vehicles/by-plate/sample-001/digital-twin", headers=self.headers())
        self.assertEqual(response.json()["vehicle"]["id"], self.vehicle_id)
        response = await self.client.get("/api/vehicles/digital-twins/resolve?plate=sample-001", headers=self.headers())
        self.assertEqual(response.json()["id"], self.vehicle_id)
        response = await self.client.get("/api/vehicles/digital-twins?query=sample-001&limit=1", headers=self.headers())
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(len(response.json()["items"]), 1)

    async def test_validation_not_found_and_date_boundaries(self):
        path = f"/api/vehicles/{self.vehicle_id}/digital-twin"
        for params in ({"history_limit": 101}, {"offset": -1}, {"as_of": "2026-10-07T10:00:00"},
                       {"from": at(8).isoformat(), "to": at(7).isoformat()}):
            response = await self.client.get(path, params=params, headers=self.headers())
            self.assertEqual(response.status_code, 422, response.text)
        response = await self.client.get(path, params={"as_of": at().isoformat()}, headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        for missing in ("/api/vehicles/9999/digital-twin", "/api/vehicles/by-plate/unknown/digital-twin",
                        "/api/vehicles/digital-twins/resolve?evidence_key=missing"):
            self.assertEqual((await self.client.get(missing, headers=self.headers())).status_code, 404)
        for params in ({}, {"plate": "sample001", "sighting_key": "one"}):
            self.assertEqual((await self.client.get("/api/vehicles/digital-twins/resolve", params=params,
                headers=self.headers())).status_code, 422)
