"""Movement trails must not turn plate guesses into vehicle identity."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx

from backend import main
from backend.access import principal_context
from backend.db_models import (CameraCheckpoint, CheckpointCrossing, Department, Detection,
                               Recognition, Sighting, TrackLink, Vehicle, VehicleEvent, VehicleTrack)
from backend.storage import DetectionStore
from db_support import authenticated_headers, make_test_engine


WHEN = datetime(2026, 10, 10, 8, tzinfo=timezone.utc)


class MovementTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())
        with self.store._lock as session:
            dept = Department(name="Movement test department")
            session.add(dept)
            session.flush()
            self.department_id = dept.id
            vehicle = Vehicle(record_key="fleet-1", normalized_plate="FLEET1", plate_number="FLEET1",
                              vehicle_id="FLEET-1", department_id=dept.id, payload={})
            other = Vehicle(record_key="fleet-2", normalized_plate="OTHER2", plate_number="OTHER2",
                            vehicle_id="FLEET-2", department_id=dept.id, payload={})
            session.add_all((vehicle, other))
            session.flush()
            self.vehicle_id, self.other_id = vehicle.id, other.id

    def tearDown(self):
        self.store.engine.dispose()

    def capture(self, camera, when, track_key, plate="FLEET1", vehicle_id=None, reviewed=True):
        with self.store._lock as session:
            event = VehicleEvent(record_key=f"event-{track_key}", camera_id=camera,
                                 vehicle_count=1, observed_at=when, payload={})
            session.add(event)
            session.flush()
            track = VehicleTrack(track_key=track_key, camera_id=camera, stream_id=camera,
                                 source_type="LIVE_FRAME", label="car", first_seen=when, last_seen=when,
                                 first_event_id=event.id, last_event_id=event.id,
                                 last_frame_number=1, last_bbox=[0, 0, 10, 10], observation_count=1)
            recognition = Recognition(record_key=f"rec-{track_key}", event_id=event.id, observed_at=when,
                plate_number=plate, confidence=0.9, review_status="ACCEPTED",
                payload={"track_id": track_key, "final_text": plate, "reviewer": "officer@test" if reviewed else ""})
            session.add_all((track, recognition))
            session.flush()
            if vehicle_id is not None:
                detection = Detection(record_key=f"det-{track_key}", recognition_id=recognition.id,
                    observed_at=when, normalized_plate=plate, payload={})
                session.add(detection)
                session.flush()
                session.add(Sighting(record_key=f"sighting-{track_key}", detection_id=detection.id,
                    vehicle_id=vehicle_id, department_id=self.department_id, observed_at=when,
                    normalized_plate=plate, status="LAWFUL",
                    payload={"camera_id": camera, "camera_area": camera, "plate_number": plate}))
            return track.id, recognition.id, event.id

    def crossing(self, camera, track_id, event_id, when):
        with self.store._lock as session:
            checkpoint = CameraCheckpoint(camera_id=camera, name=f"Gate {camera}", x1=0.5,
                y1=0, x2=0.5, y2=1, direction="BOTH", active=True, revision=1)
            session.add(checkpoint)
            session.flush()
            session.add(CheckpointCrossing(checkpoint_id=checkpoint.id, track_id=track_id,
                event_id=event_id, observed_at=when, direction="A_TO_B", revision=1,
                line_snapshot={"name": checkpoint.name}))

    def test_reviewed_anchor_and_direct_confirmed_link_build_ordered_trail(self):
        first, first_rec, first_event = self.capture("CAM-A", WHEN, "track-a", vehicle_id=self.vehicle_id)
        second, second_rec, second_event = self.capture("CAM-B", WHEN + timedelta(minutes=5), "track-b")
        self.crossing("CAM-A", first, first_event, WHEN + timedelta(minutes=1))
        self.crossing("CAM-B", second, second_event, WHEN + timedelta(minutes=6))
        with self.store._lock as session:
            session.add(TrackLink(first_track_id=first, second_track_id=second,
                first_recognition_id=first_rec, second_recognition_id=second_rec,
                normalized_plate="FLEET1", elapsed_seconds=300,
                confirmed_by="admin@test", confirmed_at=WHEN + timedelta(minutes=7)))
        trail = self.store.vehicle_movement_trail(self.vehicle_id)
        self.assertEqual(trail["total"], 4)
        self.assertEqual([row["kind"] for row in trail["items"]],
            ["checkpoint_crossing", "confirmed_link", "checkpoint_crossing", "sighting"])
        self.assertEqual(trail["items"][0]["association"], "administrator_confirmed")
        self.assertEqual(trail["items"][2]["association"], "reviewed_plate")
        self.assertEqual(self.store.vehicle_movement_trail(self.vehicle_id,
            start=WHEN + timedelta(minutes=5), limit=1)["total"], 2)
        self.assertEqual(self.store.vehicle_movement_trail(self.vehicle_id, limit=1, offset=1)["items"][0]["kind"], "confirmed_link")
        token = principal_context.set({"role": "Transport Officer", "department_id": self.department_id})
        try:
            officer = self.store.vehicle_movement_trail(self.vehicle_id)
            self.assertEqual([row["kind"] for row in officer["items"]],
                ["checkpoint_crossing", "sighting"])
        finally:
            principal_context.reset(token)

    def test_unreviewed_and_unlinked_tracks_never_enter_vehicle_trail(self):
        first, _, event = self.capture("CAM-A", WHEN, "unreviewed", vehicle_id=self.vehicle_id, reviewed=False)
        second, _, second_event = self.capture("CAM-B", WHEN, "plate-only", plate="FLEET1")
        self.crossing("CAM-A", first, event, WHEN)
        self.crossing("CAM-B", second, second_event, WHEN)
        result = self.store.vehicle_movement_trail(self.vehicle_id)
        self.assertEqual([row["kind"] for row in result["items"]], ["sighting"])
        self.assertEqual(self.store.vehicle_movement_trail(self.other_id)["total"], 0)

    def test_conflicting_vehicle_and_scoped_officer_do_not_gain_linked_track(self):
        first, first_rec, _ = self.capture("CAM-A", WHEN, "own", vehicle_id=self.vehicle_id)
        second, second_rec, event = self.capture("CAM-B", WHEN + timedelta(minutes=2), "other",
                                                 vehicle_id=self.other_id)
        self.crossing("CAM-B", second, event, WHEN + timedelta(minutes=3))
        with self.store._lock as session:
            session.add(TrackLink(first_track_id=first, second_track_id=second,
                first_recognition_id=first_rec, second_recognition_id=second_rec,
                normalized_plate="FLEET1", elapsed_seconds=120,
                confirmed_by="admin@test", confirmed_at=WHEN + timedelta(minutes=4)))
        self.assertEqual(self.store.vehicle_movement_trail(self.vehicle_id)["total"], 1)
        token = principal_context.set({"role": "Transport Officer", "department_id": self.department_id})
        try:
            self.assertEqual(self.store.vehicle_movement_trail(self.vehicle_id)["total"], 1)
        finally:
            principal_context.reset(token)


class MovementApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    async def test_authentication_missing_vehicle_and_date_validation(self):
        path = "/api/vehicles/999/movement-trail"
        self.assertEqual((await self.client.get(path)).status_code, 401)
        admin = authenticated_headers(self.store, email="movement-admin@test")
        self.assertEqual((await self.client.get(path, headers=admin)).status_code, 404)
        self.assertEqual((await self.client.get(path + "?from=2026-10-10T08:00:00", headers=admin)).status_code, 422)
        self.assertEqual((await self.client.get(path + "?limit=101", headers=admin)).status_code, 422)

    async def test_department_scoping_and_auditor_read_access(self):
        with self.store._lock as session:
            own = Department(name="Movement own department")
            foreign = Department(name="Movement foreign department")
            session.add_all((own, foreign))
            session.flush()
            vehicle = Vehicle(record_key="private-vehicle", normalized_plate="PRIVATE1",
                plate_number="PRIVATE1", vehicle_id="PRIVATE-1", department_id=foreign.id, payload={})
            session.add(vehicle)
            session.flush()
            vehicle_id, own_id = vehicle.id, own.id
            session.add(Sighting(record_key="private-sighting", vehicle_id=vehicle_id,
                department_id=foreign.id, observed_at=WHEN, normalized_plate="PRIVATE1",
                status="LAWFUL", payload={"camera_id": "PRIVATE-CAM"}))
        path = f"/api/vehicles/{vehicle_id}/movement-trail"
        officer = authenticated_headers(self.store, "Transport Officer", "movement-officer@test", own_id)
        auditor = authenticated_headers(self.store, "Auditor", "movement-auditor@test")
        self.assertEqual((await self.client.get(path, headers=officer)).status_code, 404)
        response = await self.client.get(path, headers=auditor)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
