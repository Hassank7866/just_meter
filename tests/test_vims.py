import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import func, select

from backend import main
from backend.auth import create_access_token
from backend.db_models import AuditEvent, Department, Driver, DutySlip, Sighting, Vehicle, VehicleAssignment, VimsSource, VimsSyncRun
from backend.storage import DetectionStore
from backend.vims_schema import VimsBatch
from backend.vims_store import VimsConflict
from db_support import make_test_engine, authenticated_headers


def sample():
    return json.loads((Path(__file__).parents[1] / "backend/fixtures/vims_sample.json").read_text())


class VimsTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())
        self.data = sample()

    def tearDown(self):
        self.store.engine.dispose()

    def batch(self):
        return VimsBatch.model_validate(self.data)

    def apply(self):
        preview = self.store.vims_sync(self.batch(), "admin@test", preview=True)
        return self.store.vims_sync(self.batch(), "admin@test", expected_revision=preview["base_revision"])

    def next_batch(self):
        self.data["batch_id"] = "sample-002"
        self.data["exported_at"] = "2026-10-08T09:00:00+05:00"

    def count(self, model):
        with self.store._lock as session:
            return session.scalar(select(func.count()).select_from(model))

    def test_preview_is_read_only_and_apply_links_all_five_entity_types(self):
        result = self.store.vims_sync(self.batch(), "admin@test", preview=True)
        self.assertEqual(len(result["changes"]), 5)
        for model in (VimsSource, VimsSyncRun, Department, Vehicle, Driver, VehicleAssignment, DutySlip):
            self.assertEqual(self.count(model), 0)
        applied = self.apply()
        self.assertEqual(applied["status"], "APPLIED")
        for model in (VimsSource, VimsSyncRun, Department, Vehicle, Driver, VehicleAssignment, DutySlip, AuditEvent):
            self.assertEqual(self.count(model), 1)
        self.assertEqual(self.store.get_all_approved_vehicles()[0]["plate_number"], "SAMPLE001")
        with self.store._lock as session:
            assignment = session.scalar(select(VehicleAssignment))
            self.assertEqual(session.scalar(select(DutySlip)).assignment_id, assignment.id)
            self.assertEqual(assignment.vehicle_id, session.scalar(select(Vehicle)).id)

    def test_repeated_import_is_idempotent_and_batch_collision_rejected(self):
        applied = self.apply()
        duplicate = self.store.vims_sync(self.batch(), "admin@test", expected_revision=0)
        self.assertEqual(duplicate["status"], "ALREADY_APPLIED")
        self.assertEqual(duplicate["id"], applied["id"])
        self.assertEqual(self.count(VimsSyncRun), 1)
        self.data["vehicles"][0]["color"] = "Black"
        with self.assertRaisesRegex(VimsConflict, "different contents"):
            self.store.vims_sync(self.batch(), "admin@test", expected_revision=1)
        self.assertEqual(self.store.vims_history()["items"][0]["status"], "FAILED")

    def test_missing_reference_rolls_back_all_records_and_logs_failed_apply(self):
        self.data["duty_slips"][0]["assignment_external_id"] = "MISSING"
        with self.assertRaisesRegex(VimsConflict, "Unknown vehicle_assignments"):
            self.store.vims_sync(self.batch(), "admin@test", expected_revision=0)
        for model in (Department, Vehicle, Driver, VehicleAssignment, DutySlip):
            self.assertEqual(self.count(model), 0)
        self.assertEqual(self.count(VimsSyncRun), 1)
        self.assertEqual(self.store.vims_sources()[0]["revision"], 0)
        # A corrected failed batch may be retried using the same ID.
        self.data = sample()
        self.assertEqual(self.apply()["status"], "APPLIED")

    def test_plate_change_preserves_identity_and_historical_sighting(self):
        self.apply()
        with self.store._lock as session:
            vehicle = session.scalar(select(Vehicle))
            vehicle_id = vehicle.id
            session.add(Sighting(record_key="historic", payload={"plate_number": "SAMPLE001"},
                vehicle_id=vehicle.id, normalized_plate="SAMPLE001", status="LAWFUL"))
        self.next_batch()
        self.data["vehicles"][0]["plate_number"] = "SAMPLE002"
        self.apply()
        with self.store._lock as session:
            self.assertEqual(session.scalar(select(Vehicle)).id, vehicle_id)
            self.assertEqual(session.scalar(select(Vehicle)).normalized_plate, "SAMPLE002")
            sighting = session.scalar(select(Sighting))
            self.assertEqual(sighting.vehicle_id, vehicle_id)
            self.assertEqual(sighting.payload["plate_number"], "SAMPLE001")

    def test_stale_preview_and_out_of_order_exports_do_not_overwrite(self):
        first = self.store.vims_sync(self.batch(), "admin@test", preview=True)
        self.apply()
        self.next_batch()
        with self.assertRaisesRegex(VimsConflict, "changed since preview"):
            self.store.vims_sync(self.batch(), "admin@test", expected_revision=first["base_revision"])
        self.data["exported_at"] = "2026-10-01T00:00:00Z"
        with self.assertRaisesRegex(VimsConflict, "later than"):
            self.store.vims_sync(self.batch(), "admin@test", expected_revision=1)
        self.assertEqual(self.store.vims_sources()[0]["revision"], 1)

    def test_overlaps_and_duty_outside_assignment_rejected(self):
        second = copy.deepcopy(self.data["assignments"][0])
        second["external_id"] = "OVERLAP"
        self.data["assignments"].append(second)
        with self.assertRaisesRegex(VimsConflict, "Overlapping"):
            self.apply()
        self.data = sample()
        self.data["duty_slips"][0]["valid_until"] = "2026-12-01T00:00:00Z"
        with self.assertRaisesRegex(VimsConflict, "outside its assignment"):
            self.apply()
        self.assertEqual(self.count(Vehicle), 0)

    def test_retained_duty_blocks_assignment_cancellation_and_omissions_preserve_rows(self):
        self.apply()
        self.next_batch()
        self.data["duty_slips"] = []
        self.data["assignments"][0]["status"] = "CANCELLED"
        with self.assertRaisesRegex(VimsConflict, "cancelled assignment"):
            self.apply()
        self.data["assignments"] = []
        self.data["vehicles"] = []
        self.apply()
        self.assertEqual(self.count(DutySlip), 1)
        self.assertEqual(self.count(Vehicle), 1)

    def test_local_adoption_requires_opt_in_and_preserves_contacts(self):
        self.store.add_approved_vehicle({"plate_number": "SAMPLE001", "vehicle_id": "LOCAL1",
            "department": "Local Department", "authorized_areas": "Poonch Division", "officer_email": "officer@test"})
        with self.assertRaisesRegex(VimsConflict, "link_existing"):
            self.apply()
        self.data["vehicles"][0]["link_existing"] = True
        preview = self.store.vims_sync(self.batch(), "admin@test", preview=True)
        change = next(c for c in preview["changes"] if c["kind"] == "vehicles")
        self.assertEqual(change["before"]["vehicle_id"], "LOCAL1")
        self.apply()
        self.assertEqual(self.count(Vehicle), 1)
        self.assertEqual(self.store.get_all_approved_vehicles()[0]["officer_email"], "officer@test")

    def test_other_source_cannot_claim_same_plate(self):
        self.apply()
        self.data["source"] = "another-source"
        self.data["departments"][0]["name"] = "Another Department"
        self.data["vehicles"][0]["link_existing"] = True
        with self.assertRaisesRegex(VimsConflict, "another record"):
            self.apply()
        self.assertEqual(self.count(Department), 1)

    def test_registry_fields_guarded_but_local_contacts_can_be_edited(self):
        self.apply()
        self.assertFalse(self.store.update_approved_vehicle("SAMPLE001", {"plate_number": "NEW001"})[0])
        self.assertFalse(self.store.delete_approved_vehicle("SAMPLE001")[0])
        self.assertFalse(self.store.add_approved_vehicle({"plate_number": "SAMPLE001"})[0])
        self.assertTrue(self.store.update_approved_vehicle("SAMPLE001", {"officer_email": "new@test"})[0])
        self.next_batch()
        self.data["vehicles"][0]["color"] = "Black"
        self.apply()
        with self.store._lock as session:
            vehicle = session.scalar(select(Vehicle))
            self.assertEqual(vehicle.officer_email, "new@test")
            self.assertEqual(vehicle.payload["make"], "Toyota")

    def test_schema_rejects_duplicates_naive_dates_unknown_fields_and_invalid_schedule(self):
        for mutate in (
            lambda data: data["vehicles"].append(copy.deepcopy(data["vehicles"][0])),
            lambda data: data.update(exported_at="2026-10-07T09:00:00"),
            lambda data: data.update(unknown="ignored?"),
            lambda data: data["vehicles"][0].update(duty_schedule="99:99-00:00"),
            lambda data: data["assignments"][0].update(valid_until="2020-01-01T00:00:00Z"),
        ):
            data = sample()
            mutate(data)
            with self.assertRaises(ValueError):
                VimsBatch.model_validate(data)

    def test_inconsistent_department_and_inactive_assignment_rejected(self):
        self.data["departments"].append({"external_id": "OTHER", "name": "Other department"})
        self.data["drivers"][0]["department_external_id"] = "OTHER"
        with self.assertRaisesRegex(VimsConflict, "inconsistent departments"):
            self.apply()
        self.data = sample()
        self.data["vehicles"][0]["active"] = False
        with self.assertRaisesRegex(VimsConflict, "inactive records"):
            self.apply()

    def test_cancellation_and_deactivation_retain_history_and_prevent_manual_reactivation(self):
        self.apply()
        self.next_batch()
        self.data["vehicles"][0]["active"] = False
        self.data["assignments"][0]["status"] = "CANCELLED"
        self.data["duty_slips"][0]["status"] = "CANCELLED"
        self.apply()
        self.assertEqual(self.store.get_all_approved_vehicles(), [])
        self.assertEqual(self.count(Vehicle), 1)
        self.assertFalse(self.store.add_approved_vehicle({"plate_number": "SAMPLE001"})[0])
        self.assertEqual(self.store.vims_records("duty_slips")["items"][0]["status"], "CANCELLED")


class VimsApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    def headers(self, role):
        return authenticated_headers(self.store, role)

    async def test_authentication_and_all_non_admin_roles_cannot_import(self):
        self.assertEqual((await self.client.get("/api/vims/sources")).status_code, 401)
        for role in ("Auditor", "Transport Officer", "Supervisory Officer"):
            headers = self.headers(role)
            self.assertEqual((await self.client.get("/api/vims/records/vehicles", headers=headers)).status_code, 403)
            for route in ("preview", "import"):
                self.assertEqual((await self.client.post("/api/vims/" + route, headers=headers, json={})).status_code, 403)

    async def test_preview_apply_records_history_and_repeat(self):
        headers = self.headers("Administrator")
        response = await self.client.post("/api/vims/preview", headers=headers, json=sample())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.get("/api/vims/sources", headers=headers)).json(), [])
        payload = {"batch": sample(), "expected_revision": response.json()["base_revision"]}
        response = await self.client.post("/api/vims/import", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        run_id = response.json()["id"]
        detail = (await self.client.get(f"/api/vims/runs/{run_id}", headers=headers)).json()
        self.assertEqual(detail["actor"], "user@test")
        self.assertEqual(len(detail["changes"]), 5)
        for kind in ("departments", "vehicles", "drivers", "assignments", "duty_slips"):
            self.assertEqual((await self.client.get(f"/api/vims/records/{kind}", headers=headers)).json()["total"], 1)
        self.assertEqual((await self.client.post("/api/vims/import", headers=headers, json=payload)).json()["status"], "ALREADY_APPLIED")

    async def test_invalid_input_conflict_pagination_and_size(self):
        headers = self.headers("Administrator")
        self.assertEqual((await self.client.post("/api/vims/preview", headers=headers, json={})).status_code, 422)
        data = sample()
        data["drivers"][0]["department_external_id"] = "MISSING"
        self.assertEqual((await self.client.post("/api/vims/preview", headers=headers, json=data)).status_code, 409)
        self.assertEqual((await self.client.get("/api/vims/records/unknown", headers=headers)).status_code, 422)
        self.assertEqual((await self.client.get("/api/vims/runs?limit=999", headers=headers)).status_code, 422)
        with patch("backend.vims_api.MAX_IMPORT_BYTES", 10):
            self.assertEqual((await self.client.post("/api/vims/preview", headers=headers, json=sample())).status_code, 413)

    async def test_sample_and_schema_available_without_importing(self):
        headers = self.headers("Administrator")
        response = await self.client.get("/api/vims/example", headers=headers)
        self.assertEqual(response.status_code, 200)
        VimsBatch.model_validate(response.json())
        self.assertEqual((await self.client.get("/api/vims/schema", headers=headers)).json()["title"], "VimsBatch")
        self.assertEqual(self.store.vims_sources(), [])
