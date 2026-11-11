"""Real HTTP isolation across departments, historical ownership and session changes."""
import asyncio
import io
import json
import unittest
import zipfile
from datetime import datetime
from unittest.mock import patch

import httpx
from sqlalchemy import select, func, text

from backend import main
from backend.access import principal_context
from backend.auth import create_access_token, create_camera_token, create_live_feed_token
from backend.config import settings, LOCAL_TZ
from backend.db_models import AuditEvent, Department, Evidence, RiskAssessment, RiskTask, Sighting, User, Vehicle
from backend.storage import DetectionStore
from db_support import authenticated_headers, make_test_engine


class DepartmentAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patch = patch.object(main, "store", self.store)
        self.patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        self.ids, self.depts, self.cases, self.sightings = {}, {}, {}, {}
        for code, department in (("A", "Alpha"), ("B", "Beta")):
            plate = f"AJ{code}123"
            self.store.add_approved_vehicle({"plate_number": plate, "vehicle_id": code, "department": department,
                "authorized_areas": "Mzd. Division", "duty_schedule": "24/7"})
            with self.store._lock as session:
                vehicle = session.scalar(select(Vehicle).where(Vehicle.plate_number == plate))
                self.ids[code], self.depts[code] = vehicle.id, vehicle.department_id
            self.store._append("vehicle_events_path", {"event_id": f"event-{code}", "vehicle_count": 1,
                "camera_id": code, "timestamp": "2026-10-10T12:00:00+05:00"})
            self.store._append("plate_recognition_path", {"recognition_id": f"rec-{code}",
                "detection_event_id": f"event-{code}", "final_text": plate, "review_status": "ACCEPTED", "confidence": .99})
            for number in range(4):
                key = f"{code}-{number}"
                row = {"_record_key": key, "timestamp": f"2026-10-10T12:0{number}:00+05:00", "plate_number": plate,
                       "department": department, "status": "VIOLATION", "violation_id": key,
                       "recognition_id": f"rec-{code}" if number == 0 else "", "image": f"full-{code}.jpg"}
                self.store._append("csv_path", row)
                sighting = self.store._append("government_sightings_path", dict(row, detection_key=key))
                self.sightings[code] = sighting.id
            self.store._append("evidence_path", {"evidence_id": f"evidence-{code}", "department": department,
                "recognition_id": f"rec-{code}", "detection_event_id": f"event-{code}", "plate_number": plate,
                "related_violation_id": f"{code}-0", "full_image": f"full-{code}.jpg", "plate_crop": f"plates/crop-{code}.jpg"})
            (settings.snapshots_dir / f"full-{code}.jpg").write_bytes(b"full frame must not escape")
            (settings.plate_crops_dir / f"crop-{code}.jpg").write_bytes(b"authorized crop")
            self.cases[code] = self.store.create_challan_draft(self.ids[code], "system")["id"]
        self.admin = authenticated_headers(self.store, "Administrator", "admin-access@test")
        self.a = authenticated_headers(self.store, "Transport Officer", "alpha@test", self.depts["A"])
        self.b = authenticated_headers(self.store, "Transport Officer", "beta@test", self.depts["B"])
        self.supervisor = authenticated_headers(self.store, "Supervisory Officer", "supervisor-access@test", self.depts["A"])
        self.auditor = authenticated_headers(self.store, "Auditor", "auditor-access@test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patch.stop()
        self.store.engine.dispose()

    async def get(self, path, headers=None, status=200):
        response = await self.client.get(path, headers=headers or self.a)
        self.assertEqual(response.status_code, status, response.text)
        return response

    async def test_lists_totals_pagination_and_aggregate_queries_are_scoped(self):
        for path in ("/api/authorized-vehicles", "/api/government-vehicles-spotted", "/detections",
                     "/government-vehicles-spotted", "/api/evidence", "/api/anpr/recognitions", "/api/violations-summary"):
            response = await self.get(path)
            self.assertNotIn("AJB123", response.text, path)
            self.assertIn("AJA123", response.text, path)
        twins = (await self.get("/api/vehicles/digital-twins?limit=1")).json()
        self.assertEqual(twins["total"], 1)
        self.assertEqual((await self.get("/api/vehicles/digital-twins?limit=1&offset=1")).json()["items"], [])
        self.assertEqual((await self.get("/api/challans")).json()["total"], 1)
        stats = (await self.get("/api/stats")).json()
        self.assertEqual((stats["authorized_vehicles_count"], stats["violations_count"], stats["general_detections_count"]), (1, 4, 4))
        dashboard = (await self.get("/api/dashboard?start_date=2026-10-10&end_date=2026-10-10")).json()
        self.assertEqual(dashboard["department_options"], ["Alpha"])
        self.assertEqual(dashboard["summary"]["sightings"], 4)

    async def test_direct_links_and_mutations_do_not_reveal_other_departments(self):
        for path in (f"/api/vehicles/{self.ids['B']}/digital-twin", "/api/vehicles/by-plate/AJB123/digital-twin",
                     "/api/vehicles/digital-twins/resolve?evidence_key=evidence-B", "/api/evidence/evidence-B",
                     f"/api/challans/{self.cases['B']}", f"/api/challans/{self.cases['B']}/pdf",
                     f"/api/duty/observations/{self.sightings['B']}"):
            await self.get(path, status=404)
        for path, body in (("/api/evidence/evidence-B/verify", {}),
                           ("/api/challans", {"vehicle_id": self.ids["B"]})):
            response = await self.client.post(path, headers=self.a, json=body)
            self.assertEqual(response.status_code, 404, response.text)
        response = await self.client.patch("/api/evidence/evidence-B", headers=self.a,
            json={"review_status": "UNDER_REVIEW", "reviewer": "Forged", "notes": "test"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.store.get_evidence("evidence-B")["review_status"], "CAPTURED")

    async def test_crops_exports_and_full_frames_have_separate_access(self):
        self.assertEqual((await self.get("/snapshots/plates/crop-A.jpg")).content, b"authorized crop")
        for path in ("/snapshots/plates/crop-B.jpg", "/snapshots/full-A.jpg", "/snapshots/full-B.jpg"):
            await self.get(path, status=404)
        response = await self.get("/api/evidence/evidence-A/download")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertIn("images/crop-A.jpg", archive.namelist())
            self.assertNotIn("images/full-A.jpg", archive.namelist())
        await self.get("/api/evidence/evidence-B/download", status=404)
        await self.get("/api/live-camera/latest", status=403)
        for path in ("/api/live-camera/session-token", "/api/camera/session-token", "/api/camera/analyze", "/camera/frame"):
            self.assertEqual((await self.client.post(path, headers=self.a)).status_code, 403)

    async def test_reports_use_scope_for_json_csv_pdf_and_ignore_foreign_filters(self):
        base = "/api/reports/compliance?period=monthly&anchor=2026-10-10"
        data = (await self.get(base)).json()
        self.assertEqual(data["summary"]["violations"], 4)
        self.assertEqual([row["department"] for row in data["departments"]], ["Alpha"])
        response = await self.get(base + "&format=csv")
        self.assertIn("Alpha", response.text)
        self.assertNotIn("Beta", response.text)
        response = await self.get(base + "&format=pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        await self.get(base + "&department=Beta", status=422)
        all_data = (await self.get(base, self.auditor)).json()
        self.assertEqual(all_data["summary"]["violations"], 8)
        weekly = (await self.get("/api/reports/compliance?period=weekly&anchor=2026-10-10")).json()
        self.assertEqual((weekly["start_date"], weekly["end_date"]), ("2026-10-05", "2026-10-11"))

    async def test_auditor_reads_reports_and_audit_only(self):
        for path in ("/api/authorized-vehicles", "/api/challans", "/api/dashboard", "/api/evidence", "/snapshots/plates/crop-A.jpg"):
            await self.get(path, self.auditor, 403)
        await self.get("/api/reports/compliance", self.auditor)
        await self.get("/api/audit", self.auditor)
        self.assertEqual((await self.client.post("/api/users", headers=self.auditor, json={})).status_code, 403)

    async def test_account_assignment_update_disable_and_revoke_are_immediate(self):
        body = {"email": "new-officer@test", "name": "New Officer", "role": "Transport Officer", "department_id": self.depts["A"],
                "password": "temporary-test-password"}
        response = await self.client.post("/api/users", headers=self.admin, json=body)
        self.assertEqual(response.status_code, 201, response.text)
        identifier = response.json()["id"]
        login = await self.client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
        self.assertEqual(login.status_code, 200, login.text)
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        self.assertIn("AJA123", (await self.get("/api/authorized-vehicles", headers)).text)
        body.update(department_id=self.depts["B"])
        self.assertEqual((await self.client.put(f"/api/users/{identifier}", headers=self.admin, json=body)).status_code, 200)
        await self.get("/api/authorized-vehicles", headers, 401)
        login = await self.client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        self.assertNotIn("AJA123", (await self.get("/api/authorized-vehicles", headers)).text)
        self.assertEqual((await self.client.post(f"/api/users/{identifier}/revoke", headers=self.admin)).status_code, 200)
        await self.get("/api/authorized-vehicles", headers, 401)
        body.update(active=False)
        self.assertEqual((await self.client.put(f"/api/users/{identifier}", headers=self.admin, json=body)).status_code, 200)
        self.assertEqual((await self.client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]})).status_code, 401)

    async def test_account_validation_and_self_lockout(self):
        body = {"email": "missing@test", "name": "No department", "role": "Transport Officer", "password": "temporary-test-password"}
        self.assertEqual((await self.client.post("/api/users", headers=self.admin, json=body)).status_code, 422)
        self.assertEqual((await self.client.post("/api/users", headers=self.a, json=body)).status_code, 403)
        me = (await self.get("/api/auth/me", self.admin)).json()
        body.update(email=me["email"], role="Administrator", active=False)
        self.assertEqual((await self.client.put(f"/api/users/{me['id']}", headers=self.admin, json=body)).status_code, 409)

    async def test_logout_and_unregistered_or_special_tokens_cannot_read(self):
        forged = create_access_token({"email": "missing@test", "name": "Missing", "role": "Administrator"})
        await self.get("/api/authorized-vehicles", {"Authorization": "Bearer " + forged}, 401)
        for token in (create_camera_token({"sub": "alpha@test", "role": "Transport Officer"}),
                      create_live_feed_token({"sub": "alpha@test", "role": "Transport Officer"})):
            await self.get("/api/authorized-vehicles", {"Authorization": "Bearer " + token}, 401)
        self.assertEqual((await self.client.post("/api/auth/logout", headers=self.a)).status_code, 200)
        await self.get("/api/authorized-vehicles", self.a, 401)

    async def test_audit_records_actual_actor_denials_and_excludes_tokens(self):
        response = await self.client.patch("/api/evidence/evidence-A", headers=self.a,
            json={"review_status": "UNDER_REVIEW", "reviewer": "Someone Else", "notes": "Checked plate crop"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["evidence"]["reviewer"], "alpha@test")
        await self.get("/api/evidence/evidence-B", status=404)
        events = (await self.get("/api/audit", self.auditor)).json()["items"]
        self.assertTrue(any(e["action"] == "EVIDENCE_UPDATE" and e["actor"] == "alpha@test" for e in events))
        self.assertTrue(any(e["action"] == "ACCESS_DENIED" and e["details"]["status"] == 404 for e in events))
        content = json.dumps(events)
        self.assertNotIn(self.a["Authorization"].split()[1], content)
        self.assertNotIn("password_hash", content)
        self.assertNotIn("Someone Else", content)

    async def test_audit_scope_append_only_and_transaction_rollback(self):
        await self.get("/api/authorized-vehicles", self.a)
        await self.get("/api/authorized-vehicles", self.b)
        events = (await self.get("/api/audit", self.supervisor)).json()["items"]
        self.assertTrue(events)
        self.assertNotIn("beta@test", json.dumps(events))
        with self.store._lock as session:
            before = session.scalar(select(func.count()).select_from(AuditEvent))
        token = principal_context.set({"sub": "alpha@test", "role": "Transport Officer", "department_id": self.depts["A"]})
        try:
            with self.assertRaises(RuntimeError):
                with self.store._lock as session:
                    item = session.scalar(select(Evidence).where(Evidence.record_key == "evidence-A"))
                    item.review_status = "VERIFIED"
                    session.flush()
                    raise RuntimeError("rollback test")
        finally:
            principal_context.reset(token)
        with self.store._lock as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(AuditEvent)), before)
        with self.assertRaises(ValueError):
            with self.store._lock as session:
                session.scalar(select(AuditEvent).limit(1)).action = "TAMPER"
        if self.store.engine.dialect.name == "postgresql":
            with self.assertRaises(Exception):
                with self.store.engine.begin() as connection:
                    connection.execute(text("UPDATE audit_events SET action='TAMPER'"))

    async def test_vehicle_transfer_preserves_historical_department(self):
        self.store.update_approved_vehicle("AJA123", {"department": "Beta"})
        self.assertNotIn("AJA123", (await self.get("/api/authorized-vehicles")).text)
        self.assertIn("AJA123", (await self.get("/api/government-vehicles-spotted")).text)
        self.assertNotIn("AJA123", (await self.get("/api/government-vehicles-spotted", self.b)).text)
        # Historical cases cannot reveal the new department's current officer details.
        await self.get(f"/api/challans/{self.cases['A']}", status=404)
        await self.get(f"/api/challans/{self.cases['A']}", self.b, 404)

    async def test_parallel_requests_do_not_share_department_context(self):
        results = await asyncio.gather(*[self.client.get("/api/authorized-vehicles", headers=headers) for headers in [self.a, self.b] * 5])
        for index, response in enumerate(results):
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["department"], "Alpha" if index % 2 == 0 else "Beta")

    async def test_unassigned_accounts_and_unattributed_records_fail_closed(self):
        unassigned = authenticated_headers(self.store, "Transport Officer", "unassigned@test")
        # Persist a genuine unassigned account without an invalid foreign key.
        with self.store._lock as session:
            user = session.scalar(select(User).where(User.email == "unassigned@test"))
            user.department_id = None
        self.assertEqual((await self.get("/api/authorized-vehicles", unassigned)).json(), [])
        self.assertEqual((await self.get("/api/auth/me", unassigned)).json()["email"], "unassigned@test")
        self.assertEqual((await self.client.post("/api/auth/logout", headers=unassigned)).status_code, 200)
        self.store._append("evidence_path", {"evidence_id": "unknown", "department": "", "full_image": "unknown.jpg"})
        await self.get("/api/evidence/unknown", status=404)
        await self.get("/api/evidence/unknown", self.admin)

    async def test_own_profile_timeline_and_risk_task_permissions(self):
        task_ids = {}
        with self.store._lock as session:
            policy = self.store._policy(session)
            for code in ("A", "B"):
                assessment = RiskAssessment(sighting_id=self.sightings[code], policy_id=policy.id,
                    assessed_at=datetime(2026, 10, 10, tzinfo=LOCAL_TZ), score=70, level="HIGH", result={})
                session.add(assessment); session.flush()
                task = RiskTask(assessment_id=assessment.id, priority="HIGH", assigned_role="Supervisory Officer", recommended_action="CHALLAN_REVIEW")
                session.add(task); session.flush(); task_ids[code] = task.id
        profile = (await self.get(f"/api/vehicles/{self.ids['A']}/digital-twin")).json()
        self.assertEqual(profile["compliance"]["total_sightings"], 4)
        self.assertGreaterEqual(profile["timeline"]["total"], 5)
        self.assertNotIn("AJB123", json.dumps(profile))
        tasks = (await self.get("/api/risk/tasks", self.supervisor)).json()
        self.assertEqual([row["id"] for row in tasks], [task_ids["A"]])
        for code, expected in (("B", 404), ("A", 200)):
            response = await self.client.patch(f"/api/risk/tasks/{task_ids[code]}/acknowledge", headers=self.supervisor)
            self.assertEqual(response.status_code, expected, response.text)

    async def test_websocket_role_and_revocation_before_broadcast(self):
        from fastapi.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect
        with patch.object(main, "live_broadcaster", main.LiveBroadcaster()), TestClient(main.app) as client:
            token = create_live_feed_token({"sub": "alpha@test", "role": "Transport Officer"})
            with self.assertRaises(WebSocketDisconnect):
                with client.websocket_connect(f"/ws/live-camera?token={token}"):
                    pass
            token = create_live_feed_token({"sub": "admin-access@test", "role": "Administrator"})
            with client.websocket_connect(f"/ws/live-camera?token={token}") as socket:
                socket.send_text("ping")
                self.assertEqual(socket.receive_text(), "pong")
                with self.store._lock as session:
                    session.scalar(select(User).where(User.email == "admin-access@test")).token_version += 1
                client.portal.call(main.live_broadcaster.broadcast, {"private": "must not arrive"})
                with self.assertRaises(WebSocketDisconnect):
                    socket.receive_json()
