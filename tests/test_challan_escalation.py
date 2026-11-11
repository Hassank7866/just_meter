"""Enforce escalation before challan details or documents are exposed."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import httpx

os.environ.setdefault("AUTH_JWT_SECRET", "test-auth-secret-not-for-deployment")

from backend.main import app  # noqa: E402
from backend.pdf_generator import generate_challan_pdf_bytes  # noqa: E402


def _vehicle(stage_type: str, total_violations: int) -> dict:
    return {
        "plate_number": "AJK-123",
        "normalized_plate": "AJK123",
        "vehicle_id": "GOV-123",
        "department": "Transport",
        "officer_name": "Demo Officer",
        "officer_phone": "",
        "officer_email": "",
        "authorized_areas": "Mzd. Division",
        "duty_schedule": "24/7",
        "total_violations": total_violations,
        "stage_type": stage_type,
        "stage_label": "Warning #1" if stage_type == "warning" else "Challan Issued",
        "fine_amount": 0 if stage_type == "warning" else 2500,
        "challan_id": None if stage_type == "warning" else "CHL-2026-AJK123-04",
        "violations_history": [],
    }


class ChallanEscalationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        )
        response = await self.client.post(
            "/api/auth/login",
            json={"email": "admin@justmeter.gov", "password": "admin123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.headers = {"Authorization": f"Bearer {response.json()['token']}"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_warning_stage_rejects_challan_preview_and_pdf(self):
        warning = _vehicle("warning", 1)
        with patch("backend.main.store.issued_challan_data", return_value=None):
            preview = await self.client.get("/api/challan/AJK-123", headers=self.headers)
            pdf = await self.client.get("/api/challan/pdf/AJK-123", headers=self.headers)

        self.assertEqual(preview.status_code, 409)
        self.assertEqual(preview.json()["detail"], "An approved and issued challan is required")
        self.assertEqual(pdf.status_code, 409)
        self.assertEqual(pdf.json()["detail"], "An approved and issued challan is required")

    async def test_challan_stage_allows_preview_and_pdf(self):
        challan = _vehicle("challan", 4)
        with (
            patch("backend.main.store.issued_challan_data", return_value=challan | {"case_id": 1}),
            patch("backend.main.store.challan_document", return_value=("CASE-1", b"%PDF archived")),
        ):
            preview = await self.client.get("/api/challan/AJK-123", headers=self.headers)
            pdf = await self.client.get("/api/challan/pdf/AJK-123", headers=self.headers)

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["stage_type"], "challan")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.headers["content-type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_pdf_generator_refuses_warning_stage_data(self):
        with self.assertRaisesRegex(ValueError, "Challan available only after escalation"):
            generate_challan_pdf_bytes(_vehicle("warning", 1))


if __name__ == "__main__":
    unittest.main()
