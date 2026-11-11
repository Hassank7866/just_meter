"""Capture-time attribute comparison and scoped officer review."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx

from backend import main
from backend.db_models import Department, Sighting, Vehicle, VimsSource
from backend.storage import DetectionStore
from backend.vehicle_verification import compare_attributes
from db_support import authenticated_headers, make_test_engine

WHEN = datetime(2026, 10, 11, 8, tzinfo=timezone.utc)


class ComparisonTests(unittest.TestCase):
    def test_missing_and_unsupported_types_never_prove_mismatch(self):
        self.assertEqual(compare_attributes({"vehicle_type": "SUV", "color": "White"},
            {"vehicle_type": "car", "color": ""})["vehicle_type"], "UNKNOWN")
        self.assertEqual(compare_attributes({"vehicle_type": "Sedan"},
            {"vehicle_type": "car"})["vehicle_type"], "MATCH")
        self.assertEqual(compare_attributes({"vehicle_type": "Bus"},
            {"vehicle_type": "car"})["vehicle_type"], "MISMATCH")


class VerificationApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")
        with self.store._lock as session:
            department = Department(name="Verification department", active=True)
            other = Department(name="Other verification department", active=True)
            source = VimsSource(name="verification-source", revision=1,
                                exported_at=WHEN - timedelta(days=1))
            session.add_all((department, other, source))
            session.flush()
            self.department_id, self.other_department_id = department.id, other.id
            vehicle = Vehicle(record_key="verify-vehicle", normalized_plate="VERIFY1",
                plate_number="VERIFY1", vehicle_id="VERIFY-1", department_id=department.id,
                vims_source_id=source.id, vims_external_id="V-1", vims_payload={
                    "vehicle_type": "bus", "make": "Toyota", "model": "Coaster", "color": "White"}, payload={})
            session.add(vehicle)
            session.flush()
            self.vehicle_id = vehicle.id
            sighting = Sighting(record_key="verify-sighting", vehicle_id=vehicle.id,
                department_id=department.id, observed_at=WHEN, normalized_plate="VERIFY1",
                status="REVIEW_REQUIRED", payload={})
            session.add(sighting)
            session.flush()
            self.store._capture_verification(session, sighting, "car")
            session.flush()
        self.admin = authenticated_headers(self.store, email="verify-admin@test")
        self.officer = authenticated_headers(self.store, "Transport Officer", "verify-officer@test", self.department_id)
        self.foreign = authenticated_headers(self.store, "Transport Officer", "other-officer@test", self.other_department_id)
        self.auditor = authenticated_headers(self.store, "Auditor", "verify-auditor@test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    async def test_capture_review_risk_queue_and_department_isolation(self):
        path = f"/api/vehicles/{self.vehicle_id}/verifications"
        self.assertEqual((await self.client.get(path)).status_code, 401)
        self.assertEqual((await self.client.get(path, headers=self.foreign)).status_code, 404)
        response = await self.client.get(path, headers=self.officer)
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()[0]
        self.assertEqual(item["comparisons"]["vehicle_type"], "MISMATCH")
        self.assertEqual(item["status"], "REVIEW_REQUIRED")
        review_path = f"{path}/{item['id']}/review"
        payload = {"decision": "CONFIRMED_MISMATCH", "make": "Toyota", "model": "Coaster",
                   "color": "Black", "notes": "Checked archived plate crop and inspection record."}
        self.assertEqual((await self.client.post(review_path, json=payload, headers=self.auditor)).status_code, 403)
        self.assertEqual((await self.client.post(review_path, json=payload, headers=self.foreign)).status_code, 404)
        reviewed = await self.client.post(review_path, json=payload, headers=self.officer)
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()["risk_status"], "HIGH_REVIEW")
        self.assertEqual(reviewed.json()["comparisons"]["color"], "MISMATCH")
        self.assertEqual((await self.client.post(review_path, json=payload, headers=self.officer)).status_code, 409)
        queue = await self.client.get("/api/vehicle-verification/risk-queue", headers=self.admin)
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()[0]["vehicle_id"], self.vehicle_id)
        self.assertEqual((await self.client.get("/api/vehicle-verification/risk-queue", headers=self.foreign)).json(), [])

    async def test_future_registry_export_does_not_assert_capture_attributes(self):
        with self.store._lock as session:
            source = session.get(VimsSource, 1)
            source.exported_at = WHEN + timedelta(days=1)
            sighting = Sighting(record_key="verify-old-sighting", vehicle_id=self.vehicle_id,
                department_id=self.department_id, observed_at=WHEN, normalized_plate="VERIFY1",
                status="REVIEW_REQUIRED", payload={})
            session.add(sighting)
            session.flush()
            self.store._capture_verification(session, sighting, "car")
        response = await self.client.get(f"/api/vehicles/{self.vehicle_id}/verifications", headers=self.admin)
        self.assertEqual(response.json()[0]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(response.json()[0]["expected"], {})

    async def test_confirmation_requires_actual_comparable_mismatch(self):
        with self.store._lock as session:
            sighting = Sighting(record_key="verify-matching-sighting", vehicle_id=self.vehicle_id,
                department_id=self.department_id, observed_at=WHEN + timedelta(minutes=1),
                normalized_plate="VERIFY1", status="LAWFUL", payload={})
            session.add(sighting)
            session.flush()
            self.store._capture_verification(session, sighting, "bus")
        path = f"/api/vehicles/{self.vehicle_id}/verifications"
        item = (await self.client.get(path, headers=self.admin)).json()[0]
        response = await self.client.post(f"{path}/{item['id']}/review", headers=self.admin,
            json={"decision": "CONFIRMED_MISMATCH", "make": "Toyota", "model": "Coaster",
                  "color": "White", "notes": "Reviewed capture and registry details."})
        self.assertEqual(response.status_code, 409)
