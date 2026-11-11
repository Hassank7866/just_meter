"""Read-only live check of route policy access and frontend proxy."""
import json
import os

import httpx


def main():
    api = os.environ.get("ROUTE_SMOKE_API_URL", "http://backend:8000")
    with httpx.Client(timeout=20) as client:
        path = api + "/api/approved-routes"
        assert client.get(path).status_code == 401
        login = client.post(api + "/api/auth/login", json={
            "email": "admin@justmeter.gov",
            "password": os.environ.get("DEMO_ADMIN_PASSWORD", "admin123"),
        })
        assert login.status_code == 200
        headers = {"Authorization": "Bearer " + login.json()["token"]}
        response = client.get(path, headers=headers)
        assert response.status_code == 200 and isinstance(response.json(), list)
        proxy = client.get("http://frontend:5173/api/approved-routes", headers={
            **headers, "Host": "localhost:15173",
        })
        assert proxy.status_code == 200 and proxy.json() == response.json()
        print(json.dumps({"live_route_smoke": "passed", "configured_routes": len(response.json())}))


if __name__ == "__main__":
    main()
