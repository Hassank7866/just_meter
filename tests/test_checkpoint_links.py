import unittest
from datetime import timedelta
from unittest.mock import patch

import httpx
import numpy as np

from backend import main
from backend.config import get_local_now
from backend.storage import DetectionStore
from backend.tracking import crossing_direction
from db_support import authenticated_headers, make_test_engine


def car(x, y=30):
    return {"label": "car", "confidence": 0.95, "bbox": [x, y, x + 20, y + 20]}


CONFIG = {"name": "North gate", "x1": 0.5, "y1": 0, "x2": 0.5,
          "y2": 1, "direction": "BOTH", "active": True}


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())

    def tearDown(self):
        self.store.engine.dispose()

    def frame(self, camera, x, number):
        return self.store.save_vehicle_event([car(x)], camera, "Mzd. Division",
                                             "RECORDED_VIDEO", 100, 100, number, f"VIDEO-{camera}")

    def test_finite_line_direction_and_dead_band(self):
        line = (0.5, 0, 0.5, 1)
        self.assertEqual(crossing_direction(car(35)["bbox"], car(45)["bbox"], 100, 100, line), "A_TO_B")
        self.assertEqual(crossing_direction(car(45)["bbox"], car(35)["bbox"], 100, 100, line), "B_TO_A")
        self.assertIsNone(crossing_direction(car(35, 70)["bbox"], car(45, 70)["bbox"],
                                             100, 100, (0.5, 0, 0.5, 0.2)))
        self.assertIsNone(crossing_direction(car(40)["bbox"], car(45)["bbox"], 100, 100, line))

    def test_one_crossing_per_track_revision_and_camera(self):
        self.store.save_camera_checkpoint("CAM-A", CONFIG)
        first = self.frame("CAM-A", 25, 0)
        second = self.frame("CAM-A", 35, 1)
        third = self.frame("CAM-A", 45, 2)
        self.assertEqual([first["new_crossing_count"], second["new_crossing_count"],
                          third["new_crossing_count"]], [0, 0, 1])
        self.assertEqual(third["crossings"][0]["track_id"], first["detections"][0]["track_id"])
        self.assertEqual(self.frame("CAM-A", 35, 3)["new_crossing_count"], 0)
        self.assertEqual(self.frame("CAM-B", 45, 0)["new_crossing_count"], 0)
        self.assertEqual(len(self.store.list_checkpoint_crossings("CAM-A")), 1)
        saved = self.store.save_camera_checkpoint("CAM-A", dict(CONFIG, x1=0.6, x2=0.6))
        self.assertEqual(saved["revision"], 2)
        self.frame("CAM-A", 45, 4)
        crossed = self.frame("CAM-A", 55, 5)
        self.assertEqual(crossed["new_crossing_count"], 1)
        self.assertEqual([row["revision"] for row in self.store.list_checkpoint_crossings("CAM-A")], [2, 1])

    def test_direction_filter_and_validation(self):
        self.store.save_camera_checkpoint("CAM-A", dict(CONFIG, direction="B_TO_A"))
        self.frame("CAM-A", 35, 0)
        self.assertEqual(self.frame("CAM-A", 45, 1)["new_crossing_count"], 0)
        self.assertEqual(self.frame("CAM-A", 35, 2)["new_crossing_count"], 1)
        with self.assertRaises(ValueError):
            self.store.save_camera_checkpoint("CAM-A", dict(CONFIG, x1=0.5, x2=0.5, y1=0.5, y2=0.5))

    def test_reviewed_live_plates_need_confirmation_and_are_idempotent(self):
        now = get_local_now()
        keys = []
        for camera, when, reviewer in (("CAM-A", now - timedelta(minutes=5), "officer-a@test"),
                                       ("CAM-B", now, "officer-b@test")):
            event = self.store.save_vehicle_event([car(25)], camera, "Mzd. Division",
                                                  "LIVE_FRAME", 100, 100)
            key = f"REC-{camera}"
            self.store._append("plate_recognition_path", {
                "recognition_id": key, "detection_event_id": event["event_id"],
                "timestamp": when.isoformat(), "camera_id": camera,
                "track_id": event["detections"][0]["track_id"],
                "final_text": "AJK123", "review_status": "ACCEPTED", "reviewer": reviewer,
                "confidence": 0.95,
            })
            keys.append(key)
        candidates = self.store.cross_camera_candidates()
        self.assertEqual(len(candidates), 1)
        self.assertFalse(candidates[0]["confirmed"])
        result = self.store.confirm_cross_camera_link(*keys, "admin@test")
        self.assertTrue(result["confirmed"])
        self.store.confirm_cross_camera_link(*keys, "admin@test")
        self.assertEqual(len(self.store.list_cross_camera_links()), 1)
        self.assertTrue(self.store.cross_camera_candidates()[0]["confirmed"])
        self.assertEqual(len(self.store.vehicle_track_details(candidates[0]["first_track_id"])["linked_tracks"]), 1)

    def test_unreviewed_or_mismatched_plates_cannot_be_linked(self):
        keys = []
        for camera, plate, reviewer in (("CAM-A", "AJK123", "human@test"),
                                        ("CAM-B", "AJK999", "human@test"),
                                        ("CAM-C", "AJK123", "")):
            event = self.store.save_vehicle_event([car(25)], camera, "Mzd. Division",
                                                  "LIVE_FRAME", 100, 100)
            key = f"REC-{camera}"
            self.store._append("plate_recognition_path", {
                "recognition_id": key, "detection_event_id": event["event_id"],
                "timestamp": get_local_now().isoformat(), "camera_id": camera,
                "track_id": event["detections"][0]["track_id"],
                "final_text": plate, "review_status": "ACCEPTED", "reviewer": reviewer,
                "confidence": 0.95,
            })
            keys.append(key)
        self.assertEqual(self.store.cross_camera_candidates(), [])
        with self.assertRaises(ValueError):
            self.store.confirm_cross_camera_link(keys[0], keys[1], "admin@test")
        with self.assertRaises(ValueError):
            self.store.confirm_cross_camera_link(keys[0], keys[2], "admin@test")


class CheckpointApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patch = patch.object(main, "store", self.store)
        self.patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")
        self.admin = authenticated_headers(self.store, "Administrator", "tracking-admin@test")
        self.officer = authenticated_headers(self.store, "Transport Officer", "tracking-officer@test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patch.stop()
        self.store.engine.dispose()

    async def test_checkpoint_and_link_routes_are_admin_only(self):
        response = await self.client.put("/api/camera-checkpoints/CAM-A", headers=self.admin, json=CONFIG)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["revision"], 1)
        for path in ("/api/camera-checkpoints/CAM-A", "/api/checkpoint-crossings",
                     "/api/track-links/candidates", "/api/track-links"):
            response = await self.client.get(path, headers=self.officer)
            self.assertEqual(response.status_code, 403, path)
        bad = await self.client.put("/api/camera-checkpoints/CAM-A", headers=self.admin,
                                    json=dict(CONFIG, x1=1.5))
        self.assertEqual(bad.status_code, 422)
        missing = await self.client.get("/api/camera-checkpoints/CAM-B", headers=self.admin)
        self.assertEqual(missing.status_code, 404)

    async def test_recorded_video_reports_distinct_tracks_and_checkpoint_crossing(self):
        self.store.save_camera_checkpoint("CAM-A", CONFIG)

        class FakeCapture:
            def __init__(self):
                self.remaining = 3

            def isOpened(self):
                return True

            def read(self):
                if self.remaining == 0:
                    return False, None
                self.remaining -= 1
                return True, np.zeros((100, 100, 3), dtype=np.uint8)

            def release(self):
                pass

        sequence = [([car(x)], []) for x in (25, 35, 45)]
        with patch.object(main.cv2, "VideoCapture", return_value=FakeCapture()), \
             patch.object(main.detectors, "detect", side_effect=sequence):
            response = await self.client.post("/api/camera/analyze-video", headers=self.admin,
                data={"camera_id": "CAM-A", "camera_area": "Mzd. Division",
                      "sample_every_n_frames": "1", "max_analyzed_frames": "3"},
                files={"file": ("clip.mp4", b"synthetic video", "video/mp4")})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual((result["vehicles_detected"], result["unique_vehicles"],
                          result["checkpoint_crossings"]), (3, 1, 1))
        self.assertEqual([item["new_crossing_count"] for item in result["events"]], [0, 0, 1])
