"""Read-only verification endpoints and frontend proxy check on a live stack."""
import json
import os

import httpx


def main():
    with httpx.Client(timeout=20) as client:
        api = os.environ.get("VERIFICATION_SMOKE_API_URL", "http://backend:8000")
        login = client.post(api + "/api/auth/login", json={"email": "admin@justmeter.gov",
            "password": os.environ.get("DEMO_ADMIN_PASSWORD", "admin123")})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        vehicle_id = 1
        path = f"/api/vehicles/{vehicle_id}/verifications"
        assert client.get(api + path).status_code == 401
        records = client.get(api + path, headers=headers)
        assert records.status_code == 200 and isinstance(records.json(), list)
        queue = client.get(api + "/api/vehicle-verification/risk-queue", headers=headers)
        assert queue.status_code == 200 and isinstance(queue.json(), list)
        proxy = client.get("http://frontend:5173" + path,
            headers={**headers, "Host": "localhost:15173"})
        assert proxy.status_code == 200 and proxy.json() == records.json()
        print(json.dumps({"live_verification_smoke": "passed", "vehicle_id": vehicle_id,
                          "verifications": len(records.json()), "risk_queue": len(queue.json())}))


if __name__ == "__main__":
    main()
