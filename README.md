# GovTrack AJK / Just Meter

Prototype government fleet monitoring system with camera ingestion, vehicle detection and ANPR, registry and offline VIMS data, compliance review, evidence, challans, reports, and role-based access. The frontend is React/Vite, the API is FastAPI, and PostgreSQL stores application records.

## Start locally

Install Docker Desktop with Docker Compose. From the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env and set a unique AUTH_JWT_SECRET and POSTGRES_PASSWORD.
docker compose up -d --build
docker compose ps
```

Open the dashboard at <http://localhost:5173> and the API documentation at <http://localhost:8000/docs>. The demo administrator is `admin@justmeter.gov` with password `admin123` unless changed in `.env` before first startup. Change demo passwords for any shared deployment.

For required files, environment variables, alternate ports, mobile scanning, tests, and troubleshooting, follow [Developer setup](DEVELOPER_SETUP.md).

## Scope and documentation

- [Scope assessment and 18-module scorecard](docs/modules/implementation-status.md)
- [Module implementation notes](docs/modules/)
- [API catalogue](docs/fyp-api-catalogue.md)
- [Database and risk architecture](docs/database-and-risk.md)
- [Detailed Docker commands](docs/setup-and-commands.md)

The current scope estimate is **64/90 points (71.1%)** under the equal-weight module rubric. This is an implementation estimate, not an AI accuracy result or institutional acceptance. The main gaps are predictive misuse analytics, trained vehicle attribute verification, real VIMS connectors, automated notification delivery and acknowledgments, and field validation.

## Repository handoff

Commit `docker-compose.yml`, all three Dockerfiles, `.dockerignore` files, `alembic.ini`, migrations, lockfiles, `.env.example`, and the source code. Keep `.env`, snapshots, local exports, WhatsApp sessions, dependency folders, and Docker volumes private. The tracked legacy registry CSV contains vehicle records and a small number of contact fields; review it before publishing the repository publicly.
