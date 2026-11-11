import hashlib
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx
from PIL import Image
from sqlalchemy import func, select

from backend import main
from backend.auth import create_access_token
from backend.challan_api import ChallanActionRequest
from backend.config import settings
from backend.db_models import Challan, ChallanEvent, Evidence, Sighting, Vehicle
from backend.storage import DetectionStore
from db_support import make_test_engine, authenticated_headers


def principal(role="Supervisory Officer", actor="reviewer@test"):
    return {"sub": actor, "role": role}


def prepare(store, count=4):
    store._append("approved_vehicles_path", {"plate_number": "AJK123", "vehicle_id": "GOV-1",
        "department": "Original department", "authorized_areas": "Area", "duty_schedule": "24/7"})
    vehicle_id = store.twin_vehicle_id("AJK123")
    image = settings.snapshots_dir / "challan-fixture.jpg"
    Image.new("RGB", (160, 90), (30, 80, 130)).save(image)
    checksum = hashlib.sha256(image.read_bytes()).hexdigest()
    with store._lock as session:
        department_id = session.get(Vehicle, vehicle_id).department_id
        for number in range(count):
            when = datetime(2026, 10, 7, 8, tzinfo=timezone.utc) + timedelta(minutes=number)
            row = Sighting(record_key=f"sighting-{number}", vehicle_id=vehicle_id, observed_at=when, department_id=department_id,
                normalized_plate="AJK123", status="VIOLATION", violation_id=f"VIOL-{number}",
                payload={"_record_key": f"sighting-{number}", "plate_number": "AJK123", "department": "Original department",
                    "timestamp": when.isoformat(), "status": "VIOLATION", "violation_criteria": "OUTSIDE_DUTY_HOURS"})
            session.add(row)
            session.flush()
            session.add(Evidence(record_key=f"EVD-{number}", sighting_id=row.id, department_id=department_id, review_status="VERIFIED",
                case_status="ATTACHED_TO_VIOLATION", full_image=image.name, full_image_sha256=checksum,
                payload={"evidence_id": f"EVD-{number}", "full_image": image.name, "full_image_sha256": checksum}))
    return vehicle_id


def act(store, case, action, who=None, **extra):
    body = ChallanActionRequest(action=action, expected_version=case["version"], notes="Checked source records and evidence",
        review_fingerprint=case.get("review_fingerprint"), **extra)
    return store.challan_action(case["id"], body, who or principal())


class ChallanWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())
        self.vehicle_id = prepare(self.store)

    def tearDown(self):
        self.store.engine.dispose()

    def draft(self):
        return self.store.create_challan_draft(self.vehicle_id, "preparer@test")

    def issued(self):
        case = act(self.store, self.draft(), "approve")
        return act(self.store, case, "issue", principal("Transport Officer", "issuer@test"))

    def test_idempotent_draft_threshold_and_future_observations(self):
        draft = self.draft()
        again = self.draft()
        self.assertEqual(draft["id"], again["id"])
        self.assertEqual(draft["status"], "DRAFT")
        self.assertEqual(self.store.list_challans()["total"], 1)
        self.assertEqual(len(again["history"]), 1)
        with self.store._lock as session:
            first = session.scalar(select(Sighting).order_by(Sighting.id))
            self.assertIsNone(self.store._ensure_challan_draft(session, first))
        self.assertIsNone(self.store.issued_challan_data("AJK123"))
        with self.assertRaisesRegex(ValueError, "issued"):
            self.store.challan_document(draft["id"])

    def test_separate_preparer_approver_and_role_enforcement(self):
        draft = self.draft()
        for who in (principal("Auditor"), principal("Transport Officer")):
            with self.assertRaises(PermissionError):
                act(self.store, draft, "approve", who)
        with self.assertRaisesRegex(PermissionError, "different officer"):
            act(self.store, draft, "approve", principal("Administrator", "preparer@test"))
        self.assertEqual(self.store.challan_detail(draft["id"])["status"], "DRAFT")

    def test_lifecycle_fixed_document_history_and_digital_twin(self):
        issued = self.issued()
        reference, document = self.store.challan_document(issued["id"])
        self.assertTrue(document.startswith(b"%PDF"))
        self.assertEqual(hashlib.sha256(document).hexdigest(), issued["document_sha256"])
        self.assertEqual([e["action"] for e in issued["history"]], ["CREATED", "APPROVE", "ISSUE"])
        with self.store._lock as session:
            vehicle = session.get(Vehicle, self.vehicle_id)
            vehicle.plate_number, vehicle.normalized_plate = "NEW456", "NEW456"
            vehicle.active = False
        self.assertEqual(self.store.challan_document(issued["id"])[1], document)
        self.assertEqual(self.store.issued_challan_data("AJK123", reference)["plate_number"], "AJK123")
        self.assertIsNotNone(self.store.issued_challan_data("NEW456", reference))
        self.assertIsNone(self.store.issued_challan_data("OTHER", reference))
        events = self.store.vehicle_digital_twin(self.vehicle_id)["timeline"]["items"]
        self.assertEqual(len([event for event in events if event["kind"] == "challan"]), 3)

    def test_versions_repeated_issue_and_wrong_transitions(self):
        draft = self.draft()
        with self.assertRaisesRegex(ValueError, "Cannot issue"):
            act(self.store, draft, "issue")
        approved = act(self.store, draft, "approve")
        with self.assertRaisesRegex(ValueError, "Case changed"):
            act(self.store, draft, "approve")
        issued = act(self.store, approved, "issue")
        with self.assertRaisesRegex(ValueError, "Cannot issue"):
            act(self.store, issued, "issue")
        self.assertEqual(len(self.store.challan_detail(issued["id"])["history"]), 3)

    def test_evidence_review_missing_file_and_tamper_block_approval(self):
        draft = self.draft()
        with self.store._lock as session:
            session.scalar(select(Evidence).order_by(Evidence.id.desc())).review_status = "CAPTURED"
        draft = self.store.challan_detail(draft["id"])
        with self.assertRaisesRegex(ValueError, "verified evidence"):
            act(self.store, draft, "approve")
        with self.store._lock as session:
            session.scalar(select(Evidence).order_by(Evidence.id.desc())).review_status = "VERIFIED"
        draft = self.store.challan_detail(draft["id"])
        (settings.snapshots_dir / "challan-fixture.jpg").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            act(self.store, draft, "approve")
        with self.store._lock as session:
            session.scalar(select(Evidence)).full_image = "missing-test-image.jpg"
        draft = self.store.challan_detail(draft["id"])
        with self.assertRaisesRegex(ValueError, "missing"):
            act(self.store, draft, "approve")

    def test_changed_inputs_block_stale_review_and_issuance_then_reopen(self):
        draft = self.draft()
        with self.store._lock as session:
            session.get(Vehicle, self.vehicle_id).officer_name = "New officer"
        with self.assertRaisesRegex(ValueError, "changed"):
            act(self.store, draft, "approve")
        approved = act(self.store, self.store.challan_detail(draft["id"]), "approve")
        with self.store._lock as session:
            session.get(Vehicle, self.vehicle_id).officer_name = "Another officer"
        with self.assertRaisesRegex(ValueError, "changed"):
            act(self.store, approved, "issue")
        reopened = act(self.store, approved, "reopen")
        self.assertEqual(reopened["status"], "DRAFT")
        self.assertIsNone(reopened["approved_by"])
        self.assertEqual(act(self.store, reopened, "approve")["status"], "APPROVED")

    def test_fine_amendment_requires_new_independent_approval_and_is_audited(self):
        draft = self.draft()
        amended = act(self.store, draft, "amend", principal("Administrator", "editor@test"), fine_amount=3000)
        self.assertEqual(amended["fine_amount"], 3000)
        self.assertEqual(amended["created_by"], "preparer@test")
        self.assertEqual(amended["prepared_by"], "editor@test")
        with self.assertRaises(PermissionError):
            act(self.store, amended, "approve", principal("Administrator", "editor@test"))
        approved = act(self.store, amended, "approve")
        with self.assertRaises(ValueError):
            act(self.store, approved, "amend", principal("Administrator"), fine_amount=1)
        self.assertEqual(amended["history"][-1]["details"]["previous_fine"], 2500)

    def test_appeal_suspends_dispatch_independent_resolution_and_archive(self):
        issued = self.issued()
        appealed = act(self.store, issued, "appeal", principal("Transport Officer", "appellant@test"))
        self.assertIsNone(self.store.issued_challan_data("AJK123", issued["reference"]))
        for actor in ("reviewer@test", "issuer@test", "appellant@test"):
            with self.assertRaises(PermissionError):
                act(self.store, appealed, "uphold", principal("Administrator", actor))
        upheld = act(self.store, appealed, "uphold", principal("Administrator", "appeal-reviewer@test"))
        self.assertEqual(upheld["status"], "UPHELD")
        self.assertIsNotNone(self.store.issued_challan_data("AJK123", issued["reference"]))
        cancelled = act(self.store, upheld, "cancel", principal("Administrator", "appeal-reviewer@test"))
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertIsNone(self.store.issued_challan_data("AJK123", issued["reference"]))
        self.assertTrue(self.store.challan_document(cancelled["id"])[1].startswith(b"%PDF"))

    def test_downgraded_compliance_cannot_be_issued_and_summary_survives_plate_change(self):
        draft = self.draft()
        with self.store._lock as session:
            vehicle = session.get(Vehicle, self.vehicle_id)
            vehicle.plate_number = vehicle.normalized_plate = "NEW456"
        summary = self.store.get_violations_summary()[0]
        self.assertEqual(summary["total_violations"], 4)
        self.assertEqual(summary["tier"], "CHALLAN_ELIGIBLE")
        self.assertIsNone(summary["challan_id"])
        self.assertEqual(summary["plate_number"], "NEW456")
        approved = act(self.store, self.store.challan_detail(draft["id"]), "approve")
        with self.store._lock as session:
            session.get(Sighting, draft["sighting_id"]).status = "LAWFUL"
        with self.assertRaises(ValueError):
            act(self.store, approved, "issue")

    def test_document_failure_rolls_back_issuance_and_event(self):
        approved = act(self.store, self.draft(), "approve")
        with patch("backend.challan_store.render_issued_challan", side_effect=RuntimeError("document failure")):
            with self.assertRaises(RuntimeError):
                act(self.store, approved, "issue")
        current = self.store.challan_detail(approved["id"])
        self.assertEqual(current["status"], "APPROVED")
        self.assertIsNone(current["issued_at"])
        self.assertEqual(len(current["history"]), 2)

    def test_filtering_and_read_only_archive(self):
        case = self.issued()
        with self.store._lock as session:
            count = session.scalar(select(func.count()).select_from(ChallanEvent))
        self.assertEqual(self.store.list_challans("DRAFT")["total"], 0)
        self.assertEqual(self.store.list_challans("ISSUED", self.vehicle_id)["total"], 1)
        self.assertEqual(self.store.list_challans(offset=1)["items"], [])
        for _ in range(2):
            self.store.challan_detail(case["id"])
            self.store.challan_document(case["id"])
        with self.store._lock as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ChallanEvent)), count)


class ChallanWorkflowApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.vehicle_id = prepare(self.store)
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    def headers(self, role="Administrator", actor="admin@test"):
        return authenticated_headers(self.store, role, actor)

    async def test_authentication_roles_validation_and_missing_cases(self):
        self.assertEqual((await self.client.get("/api/challans")).status_code, 401)
        self.assertEqual((await self.client.get("/api/challans", headers=self.headers("Auditor"))).status_code, 403)
        self.assertEqual((await self.client.post("/api/challans", headers=self.headers("Auditor"), json={"vehicle_id": self.vehicle_id})).status_code, 403)
        self.assertEqual((await self.client.get("/api/challans?limit=999", headers=self.headers())).status_code, 422)
        self.assertEqual((await self.client.get("/api/challans?status=PAID", headers=self.headers())).status_code, 422)
        self.assertEqual((await self.client.get("/api/challans/9999", headers=self.headers())).status_code, 404)
        draft = (await self.client.post("/api/challans", headers=self.headers(), json={"vehicle_id": self.vehicle_id})).json()
        response = await self.client.post(f"/api/challans/{draft['id']}/actions", headers=self.headers(),
            json={"action": "approve", "expected_version": 1, "notes": "ok"})
        self.assertEqual(response.status_code, 422)
        response = await self.client.post(f"/api/challans/{draft['id']}/actions", headers=self.headers("Transport Officer"),
            json={"action": "approve", "expected_version": 1, "notes": "Reviewed all the evidence"})
        self.assertEqual(response.status_code, 403)

    async def test_count_and_client_fields_cannot_bypass_issuance(self):
        for path in ("/api/challan/AJK123", "/api/challan/pdf/AJK123"):
            self.assertEqual((await self.client.get(path, headers=self.headers())).status_code, 409)
        with patch("backend.main.get_bridge_status") as bridge:
            for message in ({"message_type": "challan", "challan_id": "fake", "violation_count": 99, "fine_amount": 1},
                            {"message_type": "warning", "violation_count": 1}):
                response = await self.client.post("/api/send-notification", headers=self.headers(),
                    json={"plate_number": "AJK123", "channel": "whatsapp_direct", **message})
                self.assertEqual(response.status_code, 409, response.text)
            bridge.assert_not_called()

    async def test_issued_delivery_uses_archived_pdf_authoritative_amount_and_audits(self):
        draft = self.store.create_challan_draft(self.vehicle_id, "preparer@test")
        issued = act(self.store, act(self.store, draft, "approve"), "issue")
        document = self.store.challan_document(issued["id"])[1]
        with patch("backend.main.get_bridge_status", return_value={"connected": True}), patch(
            "backend.main.send_bridge_document", return_value={"success": True, "message": "sent"}) as sender:
            response = await self.client.post("/api/send-notification", headers=self.headers(), json={
                "plate_number": "AJK123", "channel": "whatsapp_direct", "recipient_phone": "03000000000",
                "message_type": "challan", "challan_id": issued["reference"], "fine_amount": 1, "violation_count": 900})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(sender.call_args.kwargs["pdf_bytes"], document)
        self.assertIn("2500", sender.call_args.kwargs["caption"])
        self.assertNotIn("1Bill", sender.call_args.kwargs["caption"])
        events = self.store.challan_detail(issued["id"])["history"]
        self.assertEqual(events[-1]["details"]["outcome"], "SENT")
        # Authorized document reads do not append case actions.
        response = await self.client.get(f"/api/challans/{issued['id']}/pdf", headers=self.headers("Transport Officer"))
        self.assertEqual(response.content, document)
        self.assertEqual(len(self.store.challan_detail(issued["id"])["history"]), len(events))

    async def test_failed_delivery_is_recorded_and_appeals_block_providers(self):
        draft = self.store.create_challan_draft(self.vehicle_id, "preparer@test")
        issued = act(self.store, act(self.store, draft, "approve"), "issue")
        payload = {"plate_number": "AJK123", "channel": "whatsapp_direct", "recipient_phone": "03000000000",
                   "message_type": "challan", "challan_id": issued["reference"]}
        with patch("backend.main.get_bridge_status", return_value={"connected": True}), patch(
            "backend.main.send_bridge_document", return_value={"success": False, "error": "test provider failure"}):
            response = await self.client.post("/api/send-notification", headers=self.headers(), json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.store.challan_detail(issued["id"])["history"][-1]["details"]["outcome"], "FAILED_OR_BLOCKED")
        act(self.store, issued, "appeal", principal("Transport Officer", "appellant@test"))
        with patch("backend.main.get_bridge_status") as bridge:
            response = await self.client.post("/api/send-notification", headers=self.headers(), json=payload)
        self.assertEqual(response.status_code, 409)
        bridge.assert_not_called()
