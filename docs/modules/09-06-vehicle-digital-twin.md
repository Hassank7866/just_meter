# 9.6 Vehicle Digital Twin

Implemented 8 October 2026. The Digital Twin is a live PostgreSQL read model for one registered vehicle. It joins existing records rather than maintaining a second copy of the registry. No new table, migration, model download or Docker service is required.

## What it provides

- Searchable vehicle directory, including archived vehicles.
- Current registry identity, department, officer, appearance attributes, areas and schedule.
- All-time sighting/compliance totals and latest observed location; these are observations, not continuous GPS tracking.
- Latest persisted risk assessment and count of open officer review tasks.
- VIMS vehicle, assignment, department, driver and active duty context reconstructed at a selected time, with export age and provenance.
- Existing coverage/freshness-aware duty verification. Missing source/context remains REVIEW; a displayed active slip alone does not prove authorization.
- A paginated combined timeline of sightings, risk assessments/tasks, duty reviews, assignments, slips and linked evidence.
- Links from Fleet, Spotted Vehicles, Violations and Evidence, plus a Digital Twin navigation tab. The page refreshes every minute while visible and supports manual refresh.

## Code and responsibilities

| File / function | Responsibility |
|---|---|
| `backend/digital_twin.py`: `DigitalTwinStore` | Read model mixed into `DetectionStore` |
| `twin_vehicles` | SQL directory search and pagination, including inactive vehicles |
| `twin_vehicle_id`, `twin_reference_id` | Resolve a current plate, saved sighting key or evidence key to stable `vehicles.id` |
| `_twin_source` | Replay applied VIMS changes exported at or before the requested time; select active assignments/slips using half-open periods |
| `_twin_stream` | SQL UNION of linked event IDs/times/types; filtering/counting/pagination happens in the database |
| `_twin_event` | Serialize only the selected timeline page; include capture metadata, original duty-review decision, risk task and evidence references |
| `vehicle_digital_twin` | Assemble registry, source/duty context, summary, risk, notices and timeline in one transaction |
| `backend/digital_twin_api.py` | Authenticated router, date/pagination validation, lookup and 404 behavior |
| `frontend/src/pages/VehicleProfilePage.tsx` | Search, profile cards, source-time/area controls, history filters and timeline |
| `frontend/src/components/VehicleProfileLink.tsx` | Open the profile from an existing record |
| `frontend/src/api/client.ts` | Typed authenticated fetch helpers and reference resolution |
| `tests/test_digital_twin.py` | Identity, temporal context, relational isolation, pagination, linked records and API tests |

## APIs

All four existing officer roles may read these routes. Camera-only credentials cannot. Existing department-scoping limitations still apply.

| Method and path | Parameters / behavior |
|---|---|
| `GET /api/vehicles/digital-twins` | `query`, `limit` (1–100, default 30), `offset`; returns `{total, items}` |
| `GET /api/vehicles/digital-twins/resolve` | Exactly one of `plate`, `sighting_key`, `evidence_key`; returns `{id}` or 404 |
| `GET /api/vehicles/{vehicle_id}/digital-twin` | Stable database ID; full profile |
| `GET /api/vehicles/by-plate/{plate}/digital-twin` | Normalized current plate lookup; same profile |

Profile parameters:

- `as_of`: timezone-aware VIMS/duty context time; defaults to now.
- `camera_area`: optional observed area for the duty check; an absent area cannot establish area authorization.
- `from`, `to`: timezone-aware, inclusive **timeline event-time** bounds; `from <= to`.
- `history_limit`: 1–100, default 30; `offset >= 0`. The screen uses pages of 20.

Example: `/api/vehicles/14/digital-twin?as_of=2026-10-07T08:00:00Z&history_limit=20&offset=0`.

Response sections: `vehicle`, `source_context`, `duty_verification`, `compliance`, `latest_sighting`, `risk`, `open_tasks`, `timeline`, `warnings`, `generated_at`, `as_of`, `semantics`.

## Identity and historical meaning

`vehicles.id` owns history. A plate is only an alternate lookup, not a join key. The profile retains sightings when VIMS corrects a plate or a vehicle is archived. The frontend retains the resolved ID while a profile is open. Historical navigation prefers sighting/evidence references. An evidence record without a defensible relational link is not attributed based on matching plate text.

Evidence joins directly through `evidence.sighting_id`, or, when that is absent, through recognition → detection → sighting. Both links are deduplicated in the timeline. A sighting can include its linked detection, recognition and frame-event metadata. Unlinked/no-plate frame events are excluded.

Time meanings are explicit:

1. **Registry:** current authoritative database fields, including current department and active/archive status.
2. **VIMS context:** source changes whose `exported_at <= as_of`; future exports do not establish past source state. Assignment/slip periods include their start and exclude their end. Current source coverage confirmation still governs the separate duty-verification conclusion.
3. **Summary/risk:** all-time totals and latest saved decisions, independent of timeline filters. No synthetic assessment is created for legacy rows without a persisted risk assessment.
4. **Timeline:** observation time for sightings/evidence, assessment time for risk, review time for duty reviews, and validity-start time for assignments/slips. Assignment/slip records and review/task statuses show their latest saved state; this is not a full historical reconstruction of every table. Source-time context is available separately. Evidence ordering uses its linked sighting time, not the time a file was written.
5. **Capture attribution:** stored department/plate snapshots are displayed separately from the current registry. Duty reviews expose their preserved original decision through the API.

## Docker and verification

```powershell
docker compose build backend frontend
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
docker compose up -d --no-deps backend frontend
```

The backend runner creates a disposable PostgreSQL schema and temporary images. It does not import sample VIMS data or alter live operational records. Open **Digital Twin**, select a vehicle, or use **View vehicle profile** on an existing record. If the live VIMS tables are empty, the profile correctly displays missing-source notices; use the administrator's existing VIMS workflow when real records become available.

Validation on 8 October 2026: **103 PostgreSQL backend tests passed**, including 10 Digital Twin tests; the frontend TypeScript/Vite build passed. Rebuilt services were activated. Read-only live API, stable-reference/plate lookup, unauthenticated rejection, frontend proxy and page-module checks passed, with all database counts preserved. Browser-driven interaction/visual testing was not performed.

## Remaining scope limits

Module estimate: **4.5/5 = 90%**. Registry, compliance, VIMS/duty aggregation and the unified updated view each receive one point. Detection aggregation retains half credit: linked sightings are included, but unknown identities and no-plate event association remain unresolved. The later [Digital Challan milestone](09-15-digital-challan.md) adds case actions to the activity timeline. The [movement trail increment](09-11-movement-intelligence.md) adds a separate sequence of linked sightings, reviewed-track crossings and confirmed camera links. Payment history, immutable history for all mutable records and institutional source validation remain outstanding. A Digital Twin does not add a machine-learning model.
