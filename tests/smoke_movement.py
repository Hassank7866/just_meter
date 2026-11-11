"""Read-only live movement endpoint and frontend proxy check."""
import json
import os
from pathlib import Path
import sys

import httpx
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db_models import Sighting
from backend.main import store


def main():
    with store._lock as session:
        linked_vehicle_id = session.scalar(select(Sighting.vehicle_id).where(
            Sighting.vehicle_id.is_not(None), Sighting.observed_at.is_not(None)).limit(1))
        vehicle_id = linked_vehicle_id or 1
    with httpx.Client(base_url=os.environ.get("MOVEMENT_SMOKE_API_URL", "http://localhost:8000"), timeout=20) as client:
        path = f"/api/vehicles/{vehicle_id}/movement-trail"
        assert client.get(path).status_code == 401
        login = client.post("/api/auth/login", json={"email": "admin@justmeter.gov",
            "password": os.environ.get("DEMO_ADMIN_PASSWORD", "admin123")})
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        result = client.get(path, headers=headers)
        assert result.status_code == 200
        assert result.json()["vehicle_id"] == vehicle_id
        assert result.json()["total"] >= (1 if linked_vehicle_id is not None else 0)
        assert client.get(path, params={"from": "2026-10-11T00:00:00"},
                          headers=headers).status_code == 422
        browser = client.get("http://frontend:5173" + path,
                             headers={**headers, "Host": "localhost:15173"})
        assert browser.status_code == 200
        assert browser.json()["vehicle_id"] == vehicle_id
        panel = client.get("http://frontend:5173/src/components/MovementTrailPanel.tsx",
                           headers={"Host": "localhost:15173"})
        assert panel.status_code == 200 and "Movement trail" in panel.text
        print(json.dumps({"live_movement_smoke": "passed", "vehicle_id": vehicle_id,
                          "trail_events": result.json()["total"]}))


if __name__ == "__main__":
    main()
