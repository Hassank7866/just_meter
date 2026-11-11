from datetime import date, datetime
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import select

from backend import main
from backend.auth import create_access_token
from backend.config import LOCAL_TZ
from backend.db_models import AuditEvent, RiskAssessment, RiskTask, Vehicle
from backend.storage import DetectionStore
from db_support import make_test_engine, authenticated_headers


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patch = patch.object(main, "store", self.store)
        self.patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")
        self.day = date(2026, 10, 6)
        self.params = {"start_date": "2026-10-06", "end_date": "2026-10-06"}

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patch.stop()
        self.store.engine.dispose()

    def headers(self, role="Administrator"):
        return authenticated_headers(self.store, role, "dashboard@test.local")

    def vehicle(self, plate="AJK123", department="Transport"):
        self.store.add_approved_vehicle({"plate_number": plate, "vehicle_id": plate, "department": department,
                                        "authorized_areas": "Mzd. Division", "duty_schedule": "24/7"})

    def sighting(self, key, when="2026-10-06T12:00:00+05:00", plate="AJK123", department="Transport",
                 status="VIOLATION", level="MEDIUM", task=False, score=40):
        # Normalize incoming offsets as the live capture path does.
        when = datetime.fromisoformat(when).astimezone(LOCAL_TZ).isoformat()
        payload = {"_record_key": key, "timestamp": when, "plate_number": plate,
                   "department": department, "status": status, "risk_level": level}
        with self.store._lock as session:
            self.store._upsert(session, "csv_path", payload)
            row = self.store._upsert(session, "government_sightings_path", {**payload, "detection_key": key})
            if task:
                policy = self.store._policy(session)
                assessment = RiskAssessment(sighting_id=row.id, policy_id=policy.id,
                    assessed_at=datetime.now(LOCAL_TZ), score=score, level=level, result={})
                session.add(assessment)
                session.flush()
                review = RiskTask(assessment_id=assessment.id, priority="HIGH", assigned_role="Supervisory Officer",
                                  recommended_action="CHALLAN_REVIEW", status="OPEN")
                session.add(review)
                session.flush()
                return review.id

    def dashboard(self, department=""):
        return self.store.get_executive_dashboard(self.day, self.day, department)

    async def test_empty_defaults_and_api_validation(self):
        self.assertEqual((await self.client.get("/api/dashboard")).status_code, 401)
        response = await self.client.get("/api/dashboard", headers=self.headers())
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result["daily"]), 30)
        self.assertEqual(sum(result["summary"].values()), 0)
        self.assertEqual(result["alerts"], [])
        for params, code in [({"start_date": "invalid"}, 422),
                             ({"start_date": "2026-10-07", "end_date": "2026-10-06"}, 400),
                             ({"start_date": "2025-01-01", "end_date": "2026-10-06"}, 400),
                             ({"department": "Unknown"}, 400),
                             ({"start_date": "9999-12-31", "end_date": "9999-12-31"}, 400)]:
            response = await self.client.get("/api/dashboard", params=params, headers=self.headers())
            self.assertEqual(response.status_code, code, response.text)

    async def test_inclusive_local_dates_and_zero_filled_days(self):
        self.vehicle()
        for key, when in [("before", "2026-10-05T18:59:59+00:00"),
                          ("start", "2026-10-05T19:00:00+00:00"),
                          ("last", "2026-10-06T18:59:59+00:00"),
                          ("after", "2026-10-06T19:00:00+00:00")]:
            self.sighting(key, when)
        result = self.dashboard()
        self.assertEqual(result["summary"]["sightings"], 2)
        self.assertEqual(result["summary"]["detections"], 2)
        self.assertEqual(result["summary"]["observed_vehicles"], 1)
        self.assertEqual(result["daily"][0]["violations"], 2)
        wide = self.store.get_executive_dashboard(date(2026, 10, 4), self.day)
        self.assertEqual(wide["daily"][0]["sightings"], 0)
        self.assertEqual(len(wide["daily"]), 3)

    async def test_department_uses_capture_snapshot_after_registry_transfer(self):
        self.vehicle()
        self.sighting("historic")
        with self.store._lock as session:
            vehicle = session.scalar(select(Vehicle))
            self.store._upsert(session, "approved_vehicles_path", {**vehicle.payload, "department": "Health"})
        self.sighting("current", department="Health", status="LAWFUL")
        old = self.dashboard("Transport")
        self.assertEqual(old["summary"]["registered_vehicles"], 0)
        self.assertEqual(old["summary"]["violations"], 1)
        self.assertEqual(old["summary"]["detections"], 1)
        current = self.dashboard("Health")
        self.assertEqual(current["summary"]["registered_vehicles"], 1)
        self.assertEqual(current["summary"]["lawful"], 1)
        self.assertEqual(self.dashboard()["department_options"], ["Health", "Transport"])

    async def test_unassigned_and_unassessed_are_not_counted_as_lawful_or_low_risk(self):
        self.sighting("review", department="", status="REVIEW_REQUIRED", level="PENDING_REVIEW")
        self.sighting("unknown", department="", status="UNASSESSED", level="")
        self.sighting("violation", department="", level="")
        result = self.dashboard("Unassigned")
        self.assertEqual(result["summary"]["review_required"], 2)
        self.assertEqual(result["summary"]["lawful"], 0)
        self.assertEqual(result["risk_distribution"]["UNASSESSED"], 1)
        self.assertEqual(result["risk_distribution"]["LOW"], 0)

    async def test_escalation_keeps_prior_history_and_excludes_future(self):
        self.vehicle()
        for i in range(3):
            self.sighting(f"old-{i}", f"2026-09-0{i + 1}T12:00:00+05:00", department="Previous department")
        self.sighting("fourth")
        self.vehicle("AJK456")
        self.sighting("first", plate="AJK456")
        for i in range(4):
            self.sighting(f"future-{i}", "2026-10-07T12:00:00+05:00", plate="AJK456")
        result = self.dashboard("Transport")["summary"]
        self.assertEqual(result["violations"], 2)
        self.assertEqual(result["challan_eligible_vehicles"], 1)
        self.assertEqual(result["warning_stage_vehicles"], 1)

    async def test_alert_priority_limit_filters_and_acknowledgment_authorization(self):
        self.vehicle()
        for i in range(23):
            self.sighting(f"task-{i}", task=True, score=50 + i, level="HIGH")
        self.sighting("outside-department", department="Health", task=True, score=100)
        self.sighting("outside-date", "2026-10-07T12:00:00+05:00", task=True, score=100)
        result = self.dashboard("Transport")
        self.assertEqual(result["summary"]["open_tasks"], 23)
        self.assertEqual(len(result["alerts"]), 20)
        self.assertEqual(result["alerts"][0]["risk_score"], 72)
        self.assertEqual(result["risk_distribution"]["HIGH"], 23)
        self.assertEqual(result["legacy_risk_count"], 0)
        task_id = result["alerts"][0]["id"]
        for role in ("Auditor", "Transport Officer"):
            response = await self.client.patch(f"/api/risk/tasks/{task_id}/acknowledge", headers=self.headers(role))
            self.assertEqual(response.status_code, 403)
        for _ in range(2):
            response = await self.client.patch(f"/api/risk/tasks/{task_id}/acknowledge", headers=self.headers("Supervisory Officer"))
            self.assertEqual(response.status_code, 200, response.text)
        updated = self.dashboard("Transport")
        self.assertEqual(updated["summary"]["open_tasks"], 22)
        self.assertEqual(updated["summary"]["acknowledged_tasks"], 1)
        with self.store._lock as session:
            self.assertEqual(len(list(session.scalars(select(AuditEvent).where(AuditEvent.action == "RISK_TASK_ACKNOWLEDGED")))), 1)

    async def test_legacy_risk_and_saved_detections_are_reported_without_fabricating_tasks(self):
        self.vehicle()
        self.sighting("legacy", level="CRITICAL")
        self.store._append("csv_path", {"_record_key": "unregistered", "plate_number": "OTHER1",
                                       "timestamp": "2026-10-06T12:00:00+05:00"})
        result = self.dashboard()
        self.assertEqual(result["legacy_risk_count"], 1)
        self.assertEqual(result["daily"][0]["high_risk"], 1)
        self.assertEqual(result["summary"]["detections"], 2)
        self.assertEqual(result["summary"]["sightings"], 1)
        self.assertEqual(result["summary"]["open_tasks"], 0)

    async def test_plate_correction_and_archiving_preserve_observed_identity(self):
        self.vehicle()
        self.sighting("old-plate")
        self.store.update_approved_vehicle("AJK123", {"plate_number": "AJK999"})
        self.sighting("new-plate", plate="AJK999")
        self.store.delete_approved_vehicle("AJK999")
        result = self.dashboard()
        self.assertEqual(result["summary"]["registered_vehicles"], 0)
        self.assertEqual(result["summary"]["observed_vehicles"], 1)
        self.assertEqual(result["summary"]["warning_stage_vehicles"], 1)
