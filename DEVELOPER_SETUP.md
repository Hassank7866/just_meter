# Developer setup and handoff

## What to clone and install

Clone the whole repository. Install Docker Desktop with Docker Compose v2, then start Docker Desktop. You do not need a host Python, Node.js, PostgreSQL, or YOLO installation for the Docker path. The first backend image build downloads large CPU inference packages and can take several minutes.

These files **must be committed** for a fresh clone to start: `docker-compose.yml`, root `Dockerfile` and `.dockerignore`, `frontend/Dockerfile` and `.dockerignore`, `whatsapp-bridge/Dockerfile` and `.dockerignore`, `requirements.txt`, both `package-lock.json` files, `alembic.ini`, `migrations/`, `yolo11n.pt`, `.env.example`, `data/approved_government_vehicles.csv`, and `data/snapshots/.gitkeep`.

The original scope PDF is outside this repository at `D:\fyp\GovTrack_ScopeDocument.pdf`; the [scope assessment](docs/modules/implementation-status.md) is in the repository. Share the PDF separately with collaborators who need the original document.

These files are **created locally** and must stay out of Git: `.env`, `data/snapshots/` images, legacy detection/evidence CSV exports, database dumps, `whatsapp-bridge/auth_info/`, `node_modules/`, and build caches. PostgreSQL and WhatsApp session data use Docker named volumes. A fresh clone starts with a fresh database; existing records need a separate authorized backup/restore.

## First run

From the project root in PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting. Set `AUTH_JWT_SECRET` to a long random string and change `POSTGRES_PASSWORD` to a URL-safe value (letters, digits, `-`, `_`, or `.`). The Compose database URL inserts this password without URL encoding. Override the four `DEMO_*_PASSWORD` values before first startup when this is more than a private local demo. Password changes in `.env` do not reset users already stored in PostgreSQL.

```powershell
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The `db` and `backend` services should become healthy. Backend startup applies Alembic migrations, imports the tracked legacy registry once, and seeds demo accounts. Open:

| Service | Default address | Local override |
|---|---|---|
| Dashboard | <http://localhost:5173> | `FRONTEND_PORT` in `.env` |
| API and API docs | <http://localhost:8000>, <http://localhost:8000/docs> | Fixed host port in Compose |
| PostgreSQL for pgAdmin | `127.0.0.1:5433` | `POSTGRES_PORT` in `.env` |
| WhatsApp bridge | <http://localhost:5005> | Fixed host port in Compose |

Use `admin@justmeter.gov` and the `DEMO_ADMIN_PASSWORD` value. Default is `admin123`. Other seeded roles use `transport@justmeter.gov`, `supervisor@justmeter.gov`, and `auditor@justmeter.gov` with their corresponding `.env` passwords. An administrator should assign departments to officer accounts before checking their department data.

If ports 5173 or 5433 are occupied, set `FRONTEND_PORT` or `POSTGRES_PORT` in `.env`, then run `docker compose up -d --build` again. The frontend container still listens on 5173 and PostgreSQL on 5432 internally.

## Optional connections

**Mobile camera:** The browser camera requires HTTPS on a phone. Start the optional tunnel and read the assigned URL:

```powershell
docker compose --profile mobile up -d mobile-tunnel
docker compose logs --tail 50 mobile-tunnel
```

Copy its HTTPS URL into `MOBILE_SCANNER_URL` in `.env`, then run `docker compose up -d --force-recreate frontend`. Refresh the dashboard before using **Live Camera → Mobile Camera**. Tunnel URLs can change between starts; update `.env` and recreate the frontend if that happens. Laptop camera scanning works on `localhost` without the tunnel. A public tunnel exposes the backend; change demo passwords and signing secret before using it beyond a controlled demo.

**Email:** Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `SMTP_FROM` in `.env` only if you need outbound mail. **WhatsApp:** pair the bridge from the app or set `META_WA_PHONE_NUMBER_ID` and `META_WA_ACCESS_TOKEN` for Meta's API. Keep these credentials and the bridge session volume private. External dispatch is an optional workflow and is not needed for local testing.

Set `BASE_URL` to a recipient-accessible backend address when email links are needed outside this laptop. Its local default is `http://localhost:8000`.

**VIMS:** `backend/fixtures/vims_sample.json` demonstrates the offline import format. No institutional VIMS connection is preconfigured. Import and confirm source coverage through the VIMS screen before interpreting missing duty records as violations.

## Daily commands

```powershell
docker compose up -d
docker compose down
docker compose logs --tail 100 backend
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
```

The backend test runner uses an isolated PostgreSQL schema and requires the `db` service to be running. `docker compose down` preserves named volumes. Do not use `docker compose down -v` unless you intend to discard the local database and WhatsApp session. To apply source changes, rebuild with `docker compose up -d --build`; a restart alone runs the old image.

For migration, reporting, and more demonstration commands, see [detailed setup](docs/setup-and-commands.md). For what is and is not implemented, see the [scope assessment](docs/modules/implementation-status.md).
