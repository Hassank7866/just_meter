"""Read-only live checks (authentication/access checks append expected audit entries).

Run inside the backend container: python tests/smoke_governance.py
Never prints credentials, tokens or registry records; never sends notifications.
"""
import json
import os

import httpx


def main():
    with httpx.Client(base_url="http://localhost:8000", timeout=20) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/users").status_code == 401
        totals = {}
        for prefix, variable, default in (
            ("admin", "DEMO_ADMIN_PASSWORD", "admin123"),
            ("transport", "DEMO_TRANSPORT_PASSWORD", "transport123"),
            ("auditor", "DEMO_AUDITOR_PASSWORD", "auditor123"),
        ):
            response = client.post("/api/auth/login", json={"email": f"{prefix}@justmeter.gov",
                "password": os.environ.get(variable, default)})
            assert response.status_code == 200, f"{prefix} login failed; demo credentials may have been changed"
            headers = {"Authorization": "Bearer " + response.json()["token"]}
            me = client.get("/api/auth/me", headers=headers)
            assert me.status_code == 200
            response = client.get("/api/reports/compliance", headers=headers)
            assert response.status_code == 200
            totals[prefix] = response.json()["summary"]["registered_vehicles"]
            for format, marker in (("pdf", b"%PDF"), ("csv", b"section,")):
                export = client.get("/api/reports/compliance", params={"format": format}, headers=headers)
                assert export.status_code == 200 and export.content.startswith(marker)
            if prefix == "admin":
                assert client.get("/api/users", headers=headers).status_code == 200
                assert client.get("/api/audit", headers=headers).status_code == 200
            elif prefix == "transport":
                assert client.get("/api/users", headers=headers).status_code == 403
                assert client.get("/api/audit", headers=headers).status_code == 403
                if me.json()["department_id"] is None:
                    assert client.get("/api/authorized-vehicles", headers=headers).json() == []
            else:
                assert client.get("/api/audit", headers=headers).status_code == 200
                assert client.get("/api/authorized-vehicles", headers=headers).status_code == 403
            # Exercise the actual frontend API proxy with the same role restrictions.
            browser_headers = {**headers, "Host": "localhost:15173"}
            assert client.get("http://frontend:5173/api/reports/compliance", headers=browser_headers).status_code == 200
        assert client.get("http://frontend:5173/", headers={"Host": "localhost:15173"}).status_code == 200
        module = client.get("http://frontend:5173/src/pages/GovernancePages.tsx", headers={"Host": "localhost:15173"})
        assert module.status_code == 200 and "Compliance reports" in module.text
        print(json.dumps({"live_smoke": "passed", "registered_vehicles_by_role": totals,
                          "external_notifications_sent": 0}))


if __name__ == "__main__":
    main()
