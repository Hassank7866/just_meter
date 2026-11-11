from backend.geofencing import evaluate_geofence, point_in_polygon, validate_geofence
import unittest


SQUARE = [
    {"latitude": 34.0, "longitude": 73.0},
    {"latitude": 34.0, "longitude": 74.0},
    {"latitude": 35.0, "longitude": 74.0},
    {"latitude": 35.0, "longitude": 73.0},
]


class GeofenceTests(unittest.TestCase):
  def test_polygon_contains_inside_and_edge_points_but_rejects_outside(self):
    self.assertTrue(point_in_polygon(34.5, 73.5, SQUARE))
    self.assertTrue(point_in_polygon(34.0, 73.5, SQUARE))
    self.assertFalse(point_in_polygon(35.5, 73.5, SQUARE))


  def test_zone_plate_filter_and_missing_location_review(self):
    zone = {"camera_area": "Mzd. Division", "authorized_plates": [], "polygon": SQUARE}
    vehicle = {"plate_number": "ABC-123", "authorized_areas": "Mzd. Division"}
    self.assertEqual(evaluate_geofence(vehicle, [zone], 34.5, 73.5)["outcome"], "PASS")
    self.assertEqual(evaluate_geofence(vehicle, [zone], None, 73.5)["outcome"], "REVIEW")
    self.assertEqual(evaluate_geofence(vehicle, [{**zone, "camera_area": "Mirpur Division"}], 34.5, 73.5)["outcome"], "REVIEW")
    self.assertEqual(evaluate_geofence(vehicle, [{**zone, "authorized_plates": ["ZZZ999"]}], 34.5, 73.5)["outcome"], "REVIEW")


  def test_zone_validation_rejects_invalid_coordinates_and_duplicate_vertices(self):
    with self.assertRaisesRegex(ValueError, "distinct"):
        validate_geofence({"name": "bad", "camera_area": "Mzd. Division", "polygon": [SQUARE[0], SQUARE[0], SQUARE[1]]})


  def test_outside_point_returns_geofence_violation(self):
    zone = {"camera_area": "Mzd. Division", "authorized_plates": [], "polygon": SQUARE}
    vehicle = {"plate_number": "ABC123", "authorized_areas": "Mzd. Division"}
    result = evaluate_geofence(vehicle, [zone], 36, 73.5)
    self.assertEqual(result["outcome"], "FAIL")
    self.assertEqual(result["criteria"], "OUTSIDE_GEOFENCE")


if __name__ == "__main__":
    unittest.main()
