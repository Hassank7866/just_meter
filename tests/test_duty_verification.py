import copy
from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
import cv2
import numpy as np
from sqlalchemy import func, select

from backend import main
from backend.auth import create_access_token
from backend.compliance_engine import evaluate_compliance
from backend.config import settings
from backend.db_models import DutyReview, RiskAssessment, RiskTask, Sighting
from backend.duty_verification import CoverageRequest, DutyReviewRequest, merge_duty
from backend.storage import DetectionStore
from backend.vims_schema import VimsBatch
from db_support import make_test_engine, authenticated_headers

CAPTURE = datetime.fromisoformat("2026-10-07T12:00:00+05:00")


def example():
    data = json.loads((Path(__file__).parents[1] / "backend/fixtures/vims_sample.json").read_text())
    data["vehicles"][0]["plate_number"] = "AJK123"
    data["vehicles"][0]["duty_schedule"] = "24/7"
    return data


def apply(store, data):
    batch = VimsBatch.model_validate(data)
    preview = store.vims_sync(batch, "admin@test", preview=True)
    return store.vims_sync(batch, "admin@test", expected_revision=preview["base_revision"])


def confirm(store, revision=1, **extra):
    request = CoverageRequest(expected_revision=revision, valid_from="2026-10-01T00:00:00+05:00",
        valid_until="2026-11-01T00:00:00+05:00", **extra)
    return store.confirm_duty_coverage("sample-vims", request, "admin@test")


class DutyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = {name: getattr(settings, name) for name in ("snapshots_dir", "plate_crops_dir", "evidence_images_dir")}
        for name in self.old:
            object.__setattr__(settings, name, Path(self.temp.name) / name)
        self.store = DetectionStore(make_test_engine())
        self.data = example()
        apply(self.store, self.data)

    def tearDown(self):
        self.store.engine.dispose()
        for name, value in self.old.items():
            object.__setattr__(settings, name, value)
        self.temp.cleanup()

    def check(self, when=CAPTURE, area="Mzd. Division"):
        return self.store.verify_vehicle_duty("AJK123", when, area)

    def next_batch(self):
        self.data["batch_id"] = "sample-002"
        self.data["exported_at"] = "2026-10-07T13:00:00+05:00"

    def save(self, when=CAPTURE, area="Mzd. Division"):
        vehicle = self.store.find_approved_vehicle("AJK123")
        base = evaluate_compliance(vehicle, area, when)
        decision = merge_duty(base, self.check(when, area))
        self.store.save(np.zeros((80, 160, 3), dtype=np.uint8),
            {"plate_number": "AJK123", "recognition_id": "DUTY-CAPTURE", "confidence": .99, "bbox": [1, 1, 90, 30]},
            None, None, None, "car", area, vehicle, decision, when)
        with self.store._lock as session:
            return session.scalar(select(Sighting)).id, decision

    def test_unlinked_unconfirmed_and_out_of_coverage_require_review(self):
        self.assertEqual(self.check()["status"], "REVIEW")
        self.assertEqual(self.store.verify_vehicle_duty("UNKNOWN", CAPTURE, "Mzd. Division")["status"], "REVIEW")
        confirm(self.store)
        self.assertEqual(self.check(datetime.fromisoformat("2026-11-01T00:00:00+05:00"))["status"], "REVIEW")

    def test_presence_and_area_do_not_prove_destination_or_purpose(self):
        confirm(self.store)
        result = self.check()
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["assignment"]["external_id"], "ASN-EXAMPLE")
        self.assertEqual(result["duty_slip"]["external_id"], "DUTY-EXAMPLE")
        self.assertEqual(set(result["reviewable"]), {"DUTY_DESTINATION", "DUTY_PURPOSE"})

    def test_duty_period_start_inclusive_end_exclusive(self):
        confirm(self.store)
        start = self.check(datetime.fromisoformat("2026-10-07T09:00:00+05:00"))
        end = self.check(datetime.fromisoformat("2026-10-07T17:00:00+05:00"))
        self.assertEqual(start["duty_slip"]["external_id"], "DUTY-EXAMPLE")
        self.assertEqual(end["status"], "FAIL")
        self.assertEqual(end["rules"][-1]["criteria"], "NO_VALID_DUTY_SLIP")

    def test_future_and_stale_exports_cannot_establish_authorization(self):
        confirm(self.store, max_age_hours=24)
        before = self.check(datetime.fromisoformat("2026-10-07T08:00:00+05:00"))
        stale = self.check(datetime.fromisoformat("2026-10-08T10:00:00+05:00"))
        self.assertEqual(before["status"], "REVIEW")
        self.assertIn("future records", before["rules"][0]["message"])
        self.assertEqual(stale["status"], "REVIEW")

    def test_source_update_invalidates_coverage_and_historical_cancel_is_not_retroactive(self):
        confirm(self.store)
        original = self.check()
        self.next_batch()
        self.data["duty_slips"][0]["status"] = "CANCELLED"
        apply(self.store, self.data)
        self.assertEqual(self.check()["rules"][0]["rule_id"], "DUTY_SOURCE")
        confirm(self.store, 2)
        historical = self.check()
        current = self.check(datetime.fromisoformat("2026-10-07T14:00:00+05:00"))
        self.assertEqual(historical["duty_slip"], original["duty_slip"])
        self.assertEqual(historical["source_revision"], 1)
        self.assertEqual(current["status"], "FAIL")
        self.assertIn("cancelled", current["rules"][-1]["message"])

    def test_multiple_duty_slips_require_review(self):
        self.next_batch()
        second = copy.deepcopy(self.data["duty_slips"][0]); second["external_id"] = "SECOND"
        self.data["duty_slips"].append(second)
        apply(self.store, self.data); confirm(self.store, 2)
        self.assertIn("Multiple active duty", self.check(datetime.fromisoformat("2026-10-07T14:00:00+05:00"))["rules"][-1]["message"])

    def test_missing_duty_is_confirmed_only_with_complete_coverage(self):
        self.next_batch()
        self.data["duty_slips"][0]["status"] = "CANCELLED"
        apply(self.store, self.data)
        when = datetime.fromisoformat("2026-10-07T14:00:00+05:00")
        self.assertEqual(self.check(when)["status"], "REVIEW")
        confirm(self.store, 2)
        self.assertEqual(self.check(when)["status"], "FAIL")

    def test_no_active_assignment_is_explained(self):
        self.next_batch()
        self.data["assignments"][0]["status"] = "CANCELLED"
        self.data["duty_slips"][0]["status"] = "CANCELLED"
        apply(self.store, self.data); confirm(self.store, 2)
        result = self.check(datetime.fromisoformat("2026-10-07T14:00:00+05:00"))
        self.assertEqual(result["rules"][0]["criteria"], "ASSIGNMENT_MISMATCH")

    def test_confirmed_route_breach_not_erased_by_unknown_duty_context(self):
        _, decision = self.save(area="Poonch Division")
        self.assertEqual(decision["status"], "VIOLATION")
        self.assertEqual(decision["risk_score"], 35)
        self.assertEqual(decision["duty_verification"]["status"], "REVIEW")

    def test_duty_route_breach_integrates_risk_without_double_counting(self):
        confirm(self.store)
        _, decision = self.save(area="Poonch Division")
        self.assertEqual(decision["status"], "VIOLATION")
        self.assertEqual(decision["risk_score"], 40)
        self.assertIn("UNAUTHORIZED_DESTINATION", decision["violation_criteria"])

    def test_officer_match_resolves_review_and_preserves_original(self):
        confirm(self.store)
        identifier, original = self.save()
        self.assertEqual(original["risk_level"], "PENDING_REVIEW")
        result = self.store.review_vehicle_duty(identifier, DutyReviewRequest(destination="MATCH", purpose="MATCH",
            notes="Signed trip log and destination receipt checked"), "supervisor@test")
        self.assertEqual(result["status"], "LAWFUL")
        self.assertEqual(result["duty_verification"]["status"], "PASS")
        history = self.store.duty_observation(identifier)
        self.assertEqual(history["review"]["original"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(self.store.duty_observations()["total"], 0)

    def test_officer_mismatch_creates_risk_task_and_rejects_second_review(self):
        confirm(self.store)
        identifier, _ = self.save()
        body = DutyReviewRequest(destination="MATCH", purpose="MISMATCH", notes="Trip log confirms a private journey")
        result = self.store.review_vehicle_duty(identifier, body, "supervisor@test")
        self.assertEqual(result["status"], "VIOLATION")
        self.assertEqual(result["risk"]["risk_score"], 40)
        with self.store._lock as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(RiskTask)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(RiskAssessment)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(DutyReview)), 1)
        with self.assertRaisesRegex(ValueError, "already received"):
            self.store.review_vehicle_duty(identifier, body, "supervisor@test")

    def test_source_uncertainty_cannot_be_overridden_and_review_requires_both_answers(self):
        identifier, _ = self.save()
        body = DutyReviewRequest(destination="MATCH", purpose="MATCH", notes="Officer reviewed source details")
        with self.assertRaisesRegex(ValueError, "source correction"):
            self.store.review_vehicle_duty(identifier, body, "supervisor@test")
        with self.assertRaises(ValueError):
            DutyReviewRequest(notes="short")

    def test_persisted_snapshot_survives_later_import(self):
        confirm(self.store)
        identifier, _ = self.save()
        old = self.store.duty_observation(identifier)["current"]["duty_verification"]
        self.next_batch(); self.data["duty_slips"][0]["purpose"] = "A changed purpose"
        apply(self.store, self.data)
        self.assertEqual(self.store.duty_observation(identifier)["current"]["duty_verification"], old)


class DutyApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        apply(self.store, example())
        self.patcher = patch.object(main, "store", self.store); self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose(); self.patcher.stop(); self.store.engine.dispose()

    def headers(self, role):
        return authenticated_headers(self.store, role, "officer@test")

    async def test_coverage_permissions_revision_and_timezone(self):
        body = {"expected_revision": 1, "valid_from": "2026-10-01T00:00:00Z", "valid_until": "2026-11-01T00:00:00Z"}
        self.assertEqual((await self.client.get("/api/duty/coverage")).status_code, 401)
        for role in ("Transport Officer", "Supervisory Officer", "Auditor"):
            self.assertEqual((await self.client.put("/api/duty/coverage/sample-vims", headers=self.headers(role), json=body)).status_code, 403)
        headers = self.headers("Administrator")
        self.assertEqual((await self.client.put("/api/duty/coverage/sample-vims", headers=headers, json=body)).status_code, 200)
        body["expected_revision"] = 2
        self.assertEqual((await self.client.put("/api/duty/coverage/sample-vims", headers=headers, json=body)).status_code, 409)
        self.assertEqual((await self.client.get("/api/duty/check", headers=headers,
            params={"plate": "AJK123", "observed_at": "2026-10-07T12:00:00", "camera_area": "Mzd. Division"})).status_code, 422)

    async def test_dry_check_does_not_persist_and_officer_can_read(self):
        confirm(self.store)
        response = await self.client.get("/api/duty/check", headers=self.headers("Transport Officer"),
            params={"plate": "AJK123", "observed_at": CAPTURE.isoformat(), "camera_area": "Mzd. Division"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "REVIEW")
        self.assertEqual(self.store.duty_observations()["total"], 0)

    async def test_review_role_boundaries(self):
        body = {"destination": "MATCH", "purpose": "MATCH", "notes": "Verified supporting travel documents"}
        for role in ("Transport Officer", "Auditor"):
            self.assertEqual((await self.client.post("/api/duty/observations/1/review", headers=self.headers(role), json=body)).status_code, 403)
        response = await self.client.post("/api/duty/observations/999/review", headers=self.headers("Supervisory Officer"), json=body)
        self.assertEqual(response.status_code, 404)

    async def capture_frame(self, confidence):
        frame = np.zeros((80, 160, 3), dtype=np.uint8)
        _, encoded = cv2.imencode(".jpg", frame)
        plates = [{"plate_number": "AJK123", "raw_text": "AJK123", "confidence": confidence, "bbox": [10, 10, 90, 40]}]
        vehicles = [{"label": "car", "confidence": .99, "bbox": [0, 0, 160, 80]}]
        with patch.object(main.detectors, "detect", return_value=(vehicles, plates)), \
                patch("backend.storage.get_local_now", return_value=CAPTURE), patch.object(main, "get_local_now", return_value=CAPTURE):
            response = await self.client.post("/api/camera/analyze", headers=self.headers("Administrator"),
                files={"file": ("frame.jpg", encoded.tobytes(), "image/jpeg")}, data={"camera_area": "Mzd. Division"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["plates"][0]

    async def test_live_capture_review_updates_evidence_risk_and_saved_snapshot(self):
        confirm(self.store)
        plate = await self.capture_frame(.99)
        self.assertTrue(plate["saved"])
        self.assertEqual(plate["compliance"]["status"], "REVIEW_REQUIRED")
        queue = (await self.client.get("/api/duty/observations", headers=self.headers("Supervisory Officer"))).json()
        identifier = queue["items"][0]["id"]
        body = {"destination": "MATCH", "purpose": "MISMATCH", "notes": "Officer checked documented purpose against trip log"}
        response = await self.client.post(f"/api/duty/observations/{identifier}/review", headers=self.headers("Supervisory Officer"), json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "VIOLATION")
        evidence = self.store.get_evidence(plate["evidence_id"])
        self.assertEqual(evidence["duty_verification"]["status"], "FAIL")
        self.assertEqual(evidence["case_status"], "ATTACHED_TO_VIOLATION")
        self.assertTrue(evidence["related_violation_id"])
        history = self.store.duty_observation(identifier)
        self.assertEqual(history["review"]["original"]["duty_verification"]["status"], "REVIEW")

    async def test_manual_anpr_acceptance_uses_capture_snapshot_after_later_cancellation(self):
        plate = await self.capture_frame(.55)
        data = example(); data["batch_id"] = "later-cancel"; data["exported_at"] = "2026-10-07T13:00:00+05:00"
        data["duty_slips"][0]["status"] = "CANCELLED"
        apply(self.store, data); confirm(self.store, 2)
        response = await self.client.patch(f"/api/anpr/recognitions/{plate['recognition_id']}",
            headers=self.headers("Administrator"), json={"corrected_text": "AJK123", "status": "ACCEPTED"})
        self.assertEqual(response.status_code, 200, response.text)
        duty = response.json()["enforcement"]["compliance"]["duty_verification"]
        self.assertEqual(duty["source_revision"], 1)
        self.assertEqual(duty["duty_slip"]["status"], "ACTIVE")
        self.assertEqual(self.store.get_evidence(plate["evidence_id"])["duty_verification"], duty)
