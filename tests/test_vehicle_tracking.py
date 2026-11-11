from db_support import make_test_engine
import unittest

from backend.main import matched_vehicle_for_plate
from backend.storage import DetectionStore


def vehicle(label, x):
    return {"label": label, "confidence": 0.9, "bbox": [x, 10, x + 90, 70]}


class VehicleTrackingTests(unittest.TestCase):
    def setUp(self):
        self.store = DetectionStore(make_test_engine())

    def tearDown(self):
        self.store.engine.dispose()

    def save(self, vehicles, camera="CAM-1", stream="UPLOAD-1", frame=0):
        return self.store.save_vehicle_event(vehicles, camera, "Mzd. Division",
                                             "RECORDED_VIDEO", 640, 480, frame, stream)

    def test_stable_ids_count_unique_vehicles_and_persist_observations(self):
        first = self.save([vehicle("car", 20), vehicle("bus", 250)], frame=0)
        second = self.save([vehicle("car", 24), vehicle("bus", 246)], frame=15)
        self.assertEqual(first["new_track_count"], 2)
        self.assertEqual(second["new_track_count"], 0)
        self.assertEqual([v["track_id"] for v in first["detections"]],
                         [v["track_id"] for v in second["detections"]])
        detail = self.store.vehicle_track_details(first["detections"][0]["track_id"])
        self.assertEqual(detail["observation_count"], 2)
        self.assertEqual([item["frame_number"] for item in detail["observations"]], [0, 15])
        self.assertEqual([item["event_id"] for item in detail["observations"]],
                         [first["event_id"], second["event_id"]])

    def test_camera_stream_and_frame_gap_separate_identical_boxes(self):
        first = self.save([vehicle("car", 20)], frame=0)["detections"][0]["track_id"]
        self.assertNotEqual(first, self.save([vehicle("car", 20)], camera="CAM-2", frame=15)
                            ["detections"][0]["track_id"])
        self.assertNotEqual(first, self.save([vehicle("car", 20)], stream="UPLOAD-2", frame=15)
                            ["detections"][0]["track_id"])
        self.assertNotEqual(first, self.save([vehicle("car", 20)], frame=90)
                            ["detections"][0]["track_id"])

    def test_nearby_same_class_boxes_are_matched_once_and_plate_uses_own_box(self):
        first = self.save([vehicle("car", 20), vehicle("car", 250)], frame=0)
        second = self.save([vehicle("car", 252), vehicle("car", 23)], frame=15)
        self.assertEqual(second["new_track_count"], 0)
        self.assertEqual(second["detections"][0]["track_id"], first["detections"][1]["track_id"])
        self.assertEqual(second["detections"][1]["track_id"], first["detections"][0]["track_id"])
        match = matched_vehicle_for_plate(second["detections"], [35, 40, 55, 50])
        self.assertEqual(match["track_id"], first["detections"][0]["track_id"])
        self.assertIsNone(matched_vehicle_for_plate(second["detections"], [400, 40, 420, 50]))


if __name__ == "__main__":
    unittest.main()
