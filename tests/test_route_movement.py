"""Approved routes, contextual geofences and review-only movement findings."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from backend import main
from backend.db_models import (ApprovedRoute, Department, Detection, Recognition,
                               Sighting, Vehicle, VehicleEvent, VehicleTrack)
from backend.geofencing import evaluate_geofence, validate_geofence
from backend.movement_rules import movement_findings
from backend.route_policy import RouteRequest, route_window
from backend.storage import DetectionStore
from db_support import authenticated_headers, make_test_engine


WHEN = datetime(2026, 10, 10, 8, tzinfo=timezone.utc)
SQUARE = [{"latitude": 34, "longitude": 73}, {"latitude": 34, "longitude": 74},
          {"latitude": 35, "longitude": 74}, {"latitude": 35, "longitude": 73}]


def route(**overrides):
    return {"id": 1, "name": "Approved test route", "department_id": 1, "vehicle_id": 1,
            "valid_from": WHEN - timedelta(days=1), "valid_until": WHEN + timedelta(days=1),
            "weekdays": list(range(7)), "camera_ids": ["CAM-A", "CAM-B"],
            "camera_areas": ["Allowed"], "corridor_polygon": SQUARE,
            "require_assignment": False, "require_duty": False, "enforce_dates": True,
            "active": True, "revision": 1, "approved_at": WHEN - timedelta(days=2),
            "approved_by": "admin@test"} | overrides


class RoutePolicyTests(unittest.TestCase):
    def test_request_rejects_ambiguous_policy_and_invalid_geometry(self):
        valid = {key: value for key, value in route().items() if key not in
                 {"id", "revision", "approved_at", "approved_by"}}
        self.assertEqual(RouteRequest.model_validate(valid).camera_ids, ["CAM-A", "CAM-B"])
        for bad in ({"valid_until": valid["valid_from"]}, {"weekdays": [1, 1]},
                    {"camera_ids": [], "camera_areas": [], "corridor_polygon": []},
                    {"corridor_polygon": SQUARE[:2]}):
            with self.assertRaises(ValidationError):
                RouteRequest.model_validate(valid | bad)

    def test_approved_date_assignment_and_conflicting_routes(self):
        self.assertEqual(route_window([], WHEN)["outcome"], "NOT_APPLICABLE")
        self.assertEqual(route_window([route(approved_at=WHEN + timedelta(minutes=1))], WHEN)["outcome"], "NOT_APPLICABLE")
        self.assertEqual(route_window([route()], WHEN)["outcome"], "PASS")
        self.assertEqual(route_window([route(active=False)], WHEN)["outcome"], "NOT_APPLICABLE")
        self.assertEqual(route_window([route()], WHEN + timedelta(days=2))["criteria"], "OUTSIDE_APPROVED_DATE")
        self.assertEqual(route_window([route(require_assignment=True)], WHEN)["outcome"], "REVIEW")
        duty = {"rules": [{"rule_id": "DUTY_ASSIGNMENT", "outcome": "PASS"},
                          {"rule_id": "DUTY_PERIOD", "outcome": "PASS"}]}
        self.assertEqual(route_window([route(require_duty=True)], WHEN, duty)["outcome"], "PASS")
        self.assertEqual(route_window([route(), route(id=2)], WHEN)["outcome"], "REVIEW")

    def test_department_and_duty_scoped_geofence_is_not_an_unconditional_pass(self):
        zone = validate_geofence({"name": "Authorized", "camera_area": "Allowed", "polygon": SQUARE,
                                  "department_id": 2, "require_assignment": True})
        vehicle = {"plate_number": "ABC123", "authorized_areas": "Allowed"}
        self.assertEqual(evaluate_geofence(vehicle, [zone], 34.5, 73.5, 1)["outcome"], "REVIEW")
        self.assertEqual(evaluate_geofence(vehicle, [zone], 34.5, 73.5, 2)["outcome"], "REVIEW")
        duty = {"rules": [{"rule_id": "DUTY_ASSIGNMENT", "outcome": "PASS"}]}
        self.assertEqual(evaluate_geofence(vehicle, [zone], 34.5, 73.5, 2, duty)["outcome"], "PASS")
        restricted = validate_geofence({"name": "Restricted", "camera_area": "Allowed",
                                        "polygon": SQUARE, "kind": "RESTRICTED"})
        self.assertEqual(evaluate_geofence(vehicle, [restricted], 34.5, 73.5)["outcome"], "NOT_APPLICABLE")

    def test_findings_require_reviewed_identity_and_connected_sequence(self):
        events = [
            {"kind": "sighting", "id": 1, "at": WHEN.isoformat(), "identity_evidence": "REGISTRY_LINK",
             "camera_area": "Wrong", "camera_id": "CAM-A", "track_id": "A", "latitude": 34.5, "longitude": 73.5},
            {"kind": "sighting", "id": 2, "at": (WHEN + timedelta(minutes=1)).isoformat(),
             "identity_evidence": "MANUAL_REVIEW", "camera_area": "Allowed", "camera_id": "CAM-A",
             "track_id": "A", "latitude": 34.5, "longitude": 73.5},
            {"kind": "checkpoint_crossing", "id": 3, "at": (WHEN + timedelta(minutes=2)).isoformat(),
             "camera_id": "CAM-B", "track_id": "A"},
            {"kind": "checkpoint_crossing", "id": 4, "at": (WHEN + timedelta(minutes=3)).isoformat(),
             "camera_id": "CAM-A", "track_id": "A"},
            {"kind": "sighting", "id": 5, "at": (WHEN + timedelta(minutes=4)).isoformat(),
             "identity_evidence": "MANUAL_REVIEW", "camera_area": "Wrong", "camera_id": "CAM-A",
             "track_id": "A", "latitude": 35.5, "longitude": 73.5},
        ]
        zones = [{"kind": "RESTRICTED", "zone_id": "ZONE-1", "name": "Restricted gate",
                  "polygon": [{"latitude": 35.4, "longitude": 73.4}, {"latitude": 35.4, "longitude": 73.6},
                              {"latitude": 35.6, "longitude": 73.5}], "department_id": 1}]
        findings = movement_findings(events, [route()], zones,
            {"department_id": 1, "plate_number": "ABC123"}, lambda _: {})
        kinds = {item["kind"] for item in findings}
        self.assertEqual(kinds, {"ROUTE_DEVIATION", "BOUNDARY_CROSSING", "UNAUTHORIZED_VISIT", "ABNORMAL_SEQUENCE"})
        self.assertTrue(all(item["source_id"] != 1 for item in findings))
        self.assertTrue(all(item["status"] == "REVIEW_REQUIRED" for item in findings))

    def test_unconnected_tracks_do_not_create_sequence_or_boundary_finding(self):
        events = [
            {"kind": "checkpoint_crossing", "id": 1, "at": WHEN.isoformat(),
             "camera_id": "CAM-B", "track_id": "A"},
            {"kind": "checkpoint_crossing", "id": 2, "at": (WHEN + timedelta(minutes=1)).isoformat(),
             "camera_id": "CAM-A", "track_id": "B"},
            {"kind": "sighting", "id": 3, "at": (WHEN + timedelta(minutes=2)).isoformat(),
             "identity_evidence": "MANUAL_REVIEW", "camera_area": "Allowed", "track_id": "A",
             "latitude": 34.5, "longitude": 73.5},
            {"kind": "sighting", "id": 4, "at": (WHEN + timedelta(minutes=3)).isoformat(),
             "identity_evidence": "MANUAL_REVIEW", "camera_area": "Allowed", "track_id": "B",
             "latitude": 35.5, "longitude": 73.5},
        ]
        result = movement_findings(events, [route()], [], {"department_id": 1, "plate_number": "ABC123"}, lambda _: {})
        self.assertEqual({item["kind"] for item in result}, {"ROUTE_DEVIATION"})

    def test_reviewed_sighting_at_unapproved_camera_is_route_deviation(self):
        event = {"kind": "sighting", "id": 1, "at": WHEN.isoformat(),
                 "identity_evidence": "MANUAL_REVIEW", "camera_area": "Allowed",
                 "camera_id": "CAM-X", "track_id": "A", "latitude": 34.5, "longitude": 73.5}
        findings = movement_findings([event], [route()], [],
            {"department_id": 1, "plate_number": "ABC123"}, lambda _: {})
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["kind"], "ROUTE_DEVIATION")


class RouteMovementApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patcher = patch.object(main, "store", self.store)
        self.patcher.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")
        with self.store._lock as session:
            dept = Department(name="Route test department", active=True)
            session.add(dept)
            session.flush()
            self.department_id = dept.id
            vehicle = Vehicle(record_key="route-vehicle", normalized_plate="ROUTE1",
                plate_number="ROUTE1", vehicle_id="ROUTE-1", department_id=dept.id, payload={})
            session.add(vehicle)
            session.flush()
            self.vehicle_id = vehicle.id

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patcher.stop()
        self.store.engine.dispose()

    async def test_route_admin_api_and_reviewable_alert(self):
        body = {key: value for key, value in route(department_id=self.department_id,
                vehicle_id=self.vehicle_id).items() if key not in
                {"id", "revision", "approved_at", "approved_by"}}
        body["valid_from"] = body["valid_from"].isoformat()
        body["valid_until"] = body["valid_until"].isoformat()
        admin = authenticated_headers(self.store, email="route-admin@test")
        officer = authenticated_headers(self.store, "Transport Officer", "route-officer@test", self.department_id)
        self.assertEqual((await self.client.get("/api/approved-routes", headers=officer)).status_code, 403)
        self.assertEqual((await self.client.post("/api/approved-routes", json=body, headers=officer)).status_code, 403)
        created = await self.client.post("/api/approved-routes", json=body, headers=admin)
        self.assertEqual(created.status_code, 201, created.text)
        route_id = created.json()["id"]
        self.assertEqual(len((await self.client.get("/api/approved-routes", headers=admin)).json()), 1)
        # Policy was approved after this historical capture; only new observations can generate findings.
        with self.store._lock as session:
            session.get(ApprovedRoute, route_id).approved_at = WHEN - timedelta(days=2)
            event = VehicleEvent(record_key="route-event", camera_id="CAM-X", vehicle_count=1,
                                 observed_at=WHEN, payload={})
            session.add(event)
            session.flush()
            track = VehicleTrack(track_key="route-track", camera_id="CAM-X", stream_id="CAM-X",
                source_type="LIVE_FRAME", label="car", first_seen=WHEN, last_seen=WHEN,
                first_event_id=event.id, last_event_id=event.id, last_frame_number=1,
                last_bbox=[0, 0, 20, 20], observation_count=1)
            recognition = Recognition(record_key="route-rec", event_id=event.id, observed_at=WHEN,
                plate_number="ROUTE1", confidence=0.9, review_status="ACCEPTED",
                payload={"reviewer": "reviewer@test", "track_id": "route-track", "final_text": "ROUTE1"})
            session.add_all((track, recognition))
            session.flush()
            detection = Detection(record_key="route-det", recognition_id=recognition.id,
                                  observed_at=WHEN, normalized_plate="ROUTE1", payload={})
            session.add(detection)
            session.flush()
            session.add(Sighting(record_key="route-sighting", detection_id=detection.id,
                vehicle_id=self.vehicle_id, department_id=self.department_id, observed_at=WHEN,
                normalized_plate="ROUTE1", status="REVIEW_REQUIRED",
                payload={"camera_area": "Wrong", "camera_id": "CAM-X", "plate_number": "ROUTE1"}))
        path = f"/api/vehicles/{self.vehicle_id}/movement-trail"
        trail = await self.client.get(path, headers=officer)
        self.assertEqual(trail.status_code, 200, trail.text)
        self.assertEqual(trail.json()["alert_total"], 1)
        alert = trail.json()["alerts"][0]
        self.assertEqual(alert["kind"], "ROUTE_DEVIATION")
        review = await self.client.post(f"/api/vehicles/{self.vehicle_id}/movement-alerts/{alert['alert_key']}/review",
            json={"status": "CONFIRMED", "notes": "Reviewed camera location and source record."}, headers=officer)
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual((await self.client.get(path, headers=officer)).json()["alerts"][0]["status"], "CONFIRMED")
        changed = await self.client.put(f"/api/approved-routes/{route_id}", json=body, headers=admin)
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json()["revision"], 2)
        self.assertEqual((await self.client.get(path, headers=officer)).json()["alert_total"], 0)

    async def test_approved_date_policy_reaches_compliance_decision(self):
        with self.store._lock as session:
            session.add(ApprovedRoute(**route(department_id=self.department_id,
                vehicle_id=self.vehicle_id, valid_from=WHEN + timedelta(hours=1))))
        record = {"plate_number": "ROUTE1", "authorized_areas": "Allowed", "duty_schedule": "24/7"}
        result = main.assess_compliance(record, "Allowed", WHEN)
        self.assertEqual(result["status"], "VIOLATION")
        self.assertIn("OUTSIDE_APPROVED_DATE", result["violation_criteria"])
        self.assertEqual(next(item for item in result["rules"] if item["rule_id"] == "APPROVED_ROUTE_DATE")["outcome"], "FAIL")
