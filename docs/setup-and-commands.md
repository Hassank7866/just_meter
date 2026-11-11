# Basic Setup and Commands

For a fresh clone, start with the repository-root [Developer setup](../DEVELOPER_SETUP.md). The commands below include notes from the original demo machine; use your own `.env` port values.

## Purpose

The project runs in Docker so Python, Node.js, OpenCV, PyTorch, FastAPI, React, and other application libraries do not need to be installed directly on the host machine.

Docker Desktop and Docker Compose are the only required runtime dependencies. PostgreSQL runs as the `db` service. See [Database and risk assessment](database-and-risk.md) for the schema, migration, backup and demonstration commands.

## Services

| Service | Address | Purpose |
|---|---|---|
| Frontend dashboard | <http://localhost:5173> (configurable with `FRONTEND_PORT`) | Administrative and live-monitoring interface |
| PostgreSQL | Internal `db:5432`; host `127.0.0.1:5433` (configurable with `POSTGRES_PORT`) | Persistent relational records and versioned risk policies |
| Backend API | <http://localhost:8000> | FastAPI application and camera ingestion |
| API documentation | <http://localhost:8000/docs> | Interactive Swagger documentation |
| Laptop/mobile scanner page | <http://localhost:8000> | Direct camera capture page |
| WhatsApp bridge | <http://localhost:5005> | Optional WhatsApp session and dispatch service |
| Mobile HTTPS scanner | URL printed by optional `mobile-tunnel` service | HTTPS tunnel for mobile camera permission |

The addresses above use project defaults. Set local overrides in your ignored `.env` if those ports are unavailable. Start the optional tunnel with `docker compose --profile mobile up -d mobile-tunnel`, copy its HTTPS URL into `MOBILE_SCANNER_URL`, and recreate the frontend service.

The public tunnel works only while the computer, Docker Desktop, backend, and `mobile-tunnel` container are running.

After login, **Overview** opens the executive dashboard. Use date and department filters to inspect activity, expand daily counts, and open the operational logs. See [module 9.13](modules/09-13-executive-dashboard.md) for metric definitions and alert permissions.

The **VIMS** tab provides offline import preview/apply for administrators, with imported department, vehicle, driver, assignment and duty-slip records plus synchronization history. See [module 9.5](modules/09-05-vims-synchronization.md) for the exchange contract, APIs and Docker CLI commands. Its fictional sample is not automatically imported.

Under **VIMS → Duty verification**, administrators can confirm complete source coverage after reviewing an import. New detections then check capture-time assignments, active duty periods and approved areas. Administrators and Supervisory Officers resolve destination/purpose questions using evidence. Missing or stale source coverage returns REVIEW, while independent confirmed area/hour violations remain actionable. See [module 9.9](modules/09-09-duty-slip-verification.md) for setup and APIs.

## Demo credentials

```text
Email: admin@justmeter.gov
Password: admin123
```

These are prototype credentials and must not be used for a production deployment.

## First startup

Run all commands from the repository root:

```powershell
cd D:\fyp\just_meter
docker compose up -d --build
```

The first backend build can take several minutes because it downloads CPU-only PyTorch, OpenCV, ONNX Runtime, Ultralytics, and FastALPR dependencies. Later builds reuse Docker's cache.

Check the services:

```powershell
docker compose ps
```

The database and backend should report `healthy`. Backend startup applies Alembic migrations, imports legacy CSV/JSON once, and seeds missing demo accounts before starting the API. Original files remain available, but subsequent application changes are stored in PostgreSQL.

To connect from pgAdmin, register a server with host `127.0.0.1`, port `5433` (or your `POSTGRES_PORT`), maintenance database `just_meter`, username `just_meter`, and the `POSTGRES_PASSWORD` value from `.env`. Containers use `db:5432`.

```powershell
docker compose exec -T backend python -m backend.database_report
```

## Normal start and stop

Start existing containers:

```powershell
docker compose up -d
```

Stop and remove containers while preserving application data and Docker volumes:

```powershell
docker compose down
```

Restart services:

```powershell
docker compose restart
```

Restart one service:

```powershell
docker compose restart frontend
docker compose restart backend
docker compose restart mobile-tunnel
```

## Rebuilding after source changes

Rebuild everything:

```powershell
docker compose up -d --build
```

Rebuild only the frontend:

```powershell
docker compose build frontend
docker compose up -d --no-deps --force-recreate frontend
```

Rebuild only the backend:

```powershell
docker compose build backend
docker compose up -d --no-deps --force-recreate backend
```

## Logs

Follow all logs:

```powershell
docker compose logs -f
```

Follow individual services:

```powershell
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mobile-tunnel
docker compose logs -f whatsapp-bridge
```

Display recent logs without following:

```powershell
docker compose logs --tail 100 backend
```

The mobile tunnel log prints its HTTPS URL:

```powershell
docker compose logs mobile-tunnel
```

## Running tests inside Docker

Backend unit tests:

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
```

Frontend TypeScript and production build verification:

```powershell
docker compose run --rm --no-deps frontend npm run build
```

Python compilation verification:

```powershell
docker compose run --rm --no-deps backend python -m compileall -q backend tests
```

## Laptop camera demonstration

1. Open <http://localhost:5173> (or your configured `FRONTEND_PORT`).
2. Log in and select **Live Camera**.
3. Enter a camera identifier, such as `CHECKPOINT-01`.
4. Click **Laptop Camera**.
5. Allow camera access in the browser.
6. Click **Stop Laptop** to stop the stream.

Camera access must use `localhost` or HTTPS. If access was previously denied, open the browser's site permissions, set Camera to Allow, and reload the page.

## Mobile camera demonstration

1. Ensure Docker Desktop and all services are running.
2. From the dashboard, open **Live Camera** and click **Mobile Camera**.
3. Open the displayed HTTPS URL on the phone.
4. Select a camera area.
5. Press **Start Camera**.
6. Grant camera and location permissions.
7. Point the phone at a vehicle or number plate.
8. Observe the live frames and detections on the laptop dashboard.

The mobile device can use Wi-Fi or mobile data because the scanner is exposed through an HTTPS tunnel.

## Recorded-video demonstration

1. Open **Live Camera**.
2. Enter a camera identifier.
3. Click **Analyze Recorded Video**.
4. Select an MP4, AVI, MOV, MKV, or WebM file.
5. Wait for the analyzed-frame, detected-vehicle, and saved-event counts.

The backend samples the video instead of analyzing every frame, keeping the demo responsive on CPU-only systems.

## Runtime data

PostgreSQL stores registry records, detections, evidence metadata, geofences, users and risk records in the named `postgres-data` volume. The host `data/` directory remains mounted for snapshots and the original legacy CSV/JSON import sources. Both database records and images survive normal container restarts.

Legacy runtime files and snapshot images remain excluded from Git, including:

- `data/detections.csv`
- `data/government_vehicles_spotted.csv`
- `data/vehicle_detection_events.csv`
- `data/snapshots/*`

## Docker files and Git

Dockerfiles, Compose configuration, and `.dockerignore` files are part of the repository and must be committed for coworkers to build the app.

Check ignored Docker files with:

```powershell
git status --short --ignored
```

## Common troubleshooting

### Dashboard does not reflect recent changes

Use a hard refresh:

```text
Ctrl + F5
```

If necessary, rebuild and recreate the frontend container.

### Camera permission is denied

- Use `http://localhost:5173` (or your configured `FRONTEND_PORT`) for the laptop camera.
- Use the HTTPS tunnel for the phone camera.
- Check browser site permissions.
- Close applications that may already be using the camera.

### Mobile tunnel is unavailable

Start or restart the optional tunnel and inspect the log:

```powershell
docker compose --profile mobile up -d mobile-tunnel
docker compose logs --tail 50 mobile-tunnel
```

Quick tunnels are intended for demonstrations and do not provide a production uptime guarantee.

### Port already in use

Check ports 5173, 8000, and 5005 (adjust for your `.env`):

```powershell
Get-NetTCPConnection -State Listen -LocalPort 5173,8000,5005
```

Stop the conflicting process or change the published port in the local Compose configuration.

### View backend health

```powershell
Invoke-RestMethod http://localhost:8000/health
```

### Vehicle Digital Twin

Open the **Digital Twin** tab after signing in, or select **View vehicle profile** in Fleet, Spotted Vehicles, Violations or Evidence. Search by current plate/fleet ID; archived vehicles remain available. The page refreshes every minute while visible and offers manual refresh.

The duty/source time selects historical VIMS context; the history date filters apply to timeline events. Registry details and summary cards remain current/all-time. Empty VIMS tables produce missing-source review notices until an administrator imports and confirms valid source coverage. No migration or additional environment variable is needed for this module.

```powershell
docker compose build backend frontend
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
docker compose up -d --no-deps backend frontend
```

See [module 9.6](modules/09-06-vehicle-digital-twin.md) for API parameters, code locations and limits.

### Digital Challan

Open **Challans** or **Open Cases** from Violations. Fourth-and-later confirmed observations create drafts. An officer can also create/open a historical draft for a selected vehicle. Verify the charged observation's evidence in the Evidence screen, then have another authorized reviewer approve the case. Issuance archives a fixed PDF; appeal, uphold/cancel and delivery actions are retained in case history and the Digital Twin.

The backend applies migration `0004_challans` at startup. Use the build/test/start commands above. No existing observations are automatically issued as penalties by the migration. Notification providers must be configured to send; no payment/banking integration is included. See [module 9.15](modules/09-15-digital-challan.md) for role separation and the exact APIs.


Docker publishes the frontend on host port 5173 by default (configurable with `FRONTEND_PORT`). Vite inside the container listens on 5173.
