import unittest
from unittest.mock import patch

import httpx

from backend import main
from backend.auth import create_access_token
from backend.storage import DetectionStore
from db_support import make_test_engine, authenticated_headers


class RiskApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = DetectionStore(make_test_engine())
        self.patch = patch.object(main, "store", self.store)
        self.patch.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.patch.stop()
        self.store.engine.dispose()

    def headers(self, role):
        return authenticated_headers(self.store, role, role.lower().replace(" ", "") + "@test.local")

    async def test_policy_permissions_validation_and_stale_version(self):
        policy = (await self.client.get("/api/risk/policy", headers=self.headers("Administrator"))).json()
        payload = {"expected_version": policy["version"], "config": policy["config"]}
        denied = await self.client.put("/api/risk/policy", json=payload, headers=self.headers("Supervisory Officer"))
        self.assertEqual(denied.status_code, 403)
        accepted = await self.client.put("/api/risk/policy", json=payload, headers=self.headers("Administrator"))
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["version"], 2)
        stale = await self.client.put("/api/risk/policy", json=payload, headers=self.headers("Administrator"))
        self.assertEqual(stale.status_code, 409)
        payload["config"]["recurrence_days"] = 0
        invalid = await self.client.put("/api/risk/policy", json=payload, headers=self.headers("Administrator"))
        self.assertEqual(invalid.status_code, 422)

    async def test_legacy_history_requires_authentication(self):
        for route in ("/detections", "/government-vehicles-spotted", "/api/risk/tasks"):
            response = await self.client.get(route)
            self.assertEqual(response.status_code, 401)
        response = await self.client.patch("/api/risk/tasks/1/acknowledge", headers=self.headers("Auditor"))
        self.assertEqual(response.status_code, 403)

    async def test_database_geofence_crud_roundtrip(self):
        payload = {"name": "Test", "camera_area": "Mzd. Division", "authorized_plates": ["AJK123"],
                   "polygon": [{"latitude": 1, "longitude": 1}, {"latitude": 2, "longitude": 1}, {"latitude": 2, "longitude": 2}]}
        headers = self.headers("Administrator")
        response = await self.client.post("/api/geofences", headers=headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        zone_id = response.json()["zone_id"]
        payload["name"] = "Updated"
        response = await self.client.put(f"/api/geofences/{zone_id}", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((await self.client.get("/api/geofences", headers=headers)).json()[0]["name"], "Updated")
        self.assertEqual((await self.client.delete(f"/api/geofences/{zone_id}", headers=headers)).status_code, 200)
        self.assertEqual(self.store.get_geofences(), [])
