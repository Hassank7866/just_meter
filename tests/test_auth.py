"""HTTP-level authentication and role regression tests."""
from __future__ import annotations

import os
import unittest

import httpx

# Compose supplies the same local-development secret as the backend service.
os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret-not-for-deployment")

from backend.main import app  # noqa: E402


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def login(self, email: str, password: str) -> str:
        response = await self.client.post(
            "/api/auth/login", json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    async def test_api_without_token_returns_401(self):
        response = await self.client.get("/api/authorized-vehicles")
        self.assertEqual(response.status_code, 401)

    async def test_auditor_can_read_reports_but_not_operational_records(self):
        token = await self.login("auditor@justmeter.gov", "auditor123")
        headers = {"Authorization": f"Bearer {token}"}
        read_response = await self.client.get("/api/authorized-vehicles", headers=headers)
        write_response = await self.client.post("/api/authorized-vehicles", headers=headers, json={})
        self.assertEqual(read_response.status_code, 403)
        report = await self.client.get("/api/reports/compliance", headers=headers)
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(write_response.status_code, 403)

    async def test_transport_officer_can_review_evidence_but_cannot_manage_vehicles(self):
        token = await self.login("transport@justmeter.gov", "transport123")
        headers = {"Authorization": f"Bearer {token}"}
        review_response = await self.client.patch(
            "/api/evidence/EVD-NOT-FOUND", headers=headers,
            json={"review_status": "UNDER_REVIEW", "reviewer": "Test Officer", "notes": ""},
        )
        manage_response = await self.client.post("/api/authorized-vehicles", headers=headers, json={})
        self.assertEqual(review_response.status_code, 404)
        self.assertEqual(manage_response.status_code, 403)

    async def test_valid_admin_token_is_allowed_and_health_is_public(self):
        token = await self.login("admin@justmeter.gov", "admin123")
        response = await self.client.get(
            "/api/authorized-vehicles", headers={"Authorization": f"Bearer {token}"},
        )
        health = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(health.status_code, 200)

    async def test_snapshots_require_token(self):
        response = await self.client.get("/snapshots/not-a-real-file.jpg")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
