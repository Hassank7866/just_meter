# 9.5 VIMS synchronization foundation

Implemented 7 October 2026. This milestone provides a versioned offline JSON adapter and relational source records. It is not a connection to an institutional VIMS deployment. Source-specific API authentication, periodic database reads and read-only view adapters still require the institution's schema and access details.

## Workflow

1. Open **VIMS** in the dashboard. All four authenticated roles can inspect imported records and synchronization history; only Administrator can preview/apply imports.
2. Download the sample export or prepare a document matching **Import specification**. The sample is fictional and is not automatically seeded.
3. Select the JSON file and choose **Validate and preview**. The preview validates the entire batch and shows creations, explicit links, updates, unchanged records and before/after fields. It leaves no persisted source/registry/history rows.
4. Choose **Apply reviewed import**. The backend revalidates the document and source revision under the shared PostgreSQL transaction lock. The complete batch succeeds or its entity changes roll back.
5. Inspect the source revision, imported records and run history. Failed valid-document apply attempts are recorded with the authenticated actor; malformed documents and preview failures return validation errors without creating a run.

## Source contract

`backend/fixtures/vims_sample.json` is the complete example. `GET /api/vims/schema` returns the JSON Schema from `backend/vims_schema.py`.

| Collection | Required data and relationships |
|---|---|
| departments | Stable external ID, name; active state and explicit existing-record adoption flag |
| vehicles | Stable external ID, plate, fleet ID, department external ID, authorized areas; recurring schedule, active state, type/make/model/color |
| drivers | Stable external ID, name, department external ID and active state |
| assignments | Stable external ID, vehicle/department/driver external IDs, assigned officer name, start/end timestamps, ACTIVE/CANCELLED |
| duty_slips | Stable external ID, assignment external ID, start/end timestamps, destination, authorized areas, purpose, approving officer, ACTIVE/CANCELLED |

Every batch has `schema_version: 1`, a stable `source` namespace, a unique `batch_id`, and a timezone-aware `exported_at`. Each supplied entity is a complete record, not a field patch. Omitted collections/records are retained. Use explicit `active: false` or `status: CANCELLED` updates; there is no deletion by omission. Maximum: 5 MiB and 5,000 total records.

Entity references resolve within the same source, including previously imported records. Unknown fields, duplicate external IDs, invalid schedules, missing references, plate/name identity collisions, overlapping active assignments for one vehicle, inconsistent current departments and duty periods outside their assignment reject the batch. Periods use `[valid_from, valid_until)`; adjacent assignments are allowed. Retained duties/assignments are checked too. Current/future ACTIVE assignments require active vehicle, driver and department records; expired assignments retain their historical department context.

External IDs identify records across updates. Plate changes preserve the internal vehicle ID and existing sighting foreign keys. A matching local vehicle/department requires `link_existing: true` to adopt it; the preview shows the prior fields. A different source cannot claim that identity. Contact details, notes and manually configured risk context remain local registry fields. Administrators may edit those locally; imported plate/fleet/department/area/schedule fields must be changed through synchronization. Imported vehicles must be deactivated through synchronization.

Repeating an applied batch with the same canonical checksum returns `ALREADY_APPLIED` without new rows. Reusing an applied batch ID with different contents is rejected. A new batch must have a later export timestamp than the source's last successful import. Failed batches may be corrected and retried. The source revision prevents an older preview from overwriting a newer successful import. Previews and imports use the same validation code.

## Database and code map

Migration `0002_vims` adds `vims_sources`, `drivers`, `vehicle_assignments`, `duty_slips`, and `vims_sync_runs`. Existing `departments` and `vehicles` gain nullable source identifiers and imported snapshots; departments also gain an active flag. Existing primary keys and history are retained. Sync runs store actor, checksum, export/attempt time, result, counts, errors and before/after snapshots. Application endpoints do not edit or delete run history. These are application audit records, not a claim of database-level immutable storage.

| File | Responsibility |
|---|---|
| `backend/vims_schema.py` | Pydantic exchange contract, lengths, dates, IDs, schedules and collection validation |
| `backend/vims_store.py` | `vims_sync`, `_vims_apply`, `_vims_validate_relations`, source identity, transactions, conflicts, history and queries |
| `backend/vims_api.py` | Bounded request reading, administrator dependencies and VIMS router |
| `backend/vims_sync.py` | Container CLI adapter; preview by default, optional apply |
| `backend/db_models.py` | ORM entities and foreign keys |
| `migrations/versions/0002_vims.py` | Additive PostgreSQL migration |
| `backend/storage.py` | Source ownership checks in existing registry mutation methods |
| `frontend/src/pages/VimsPage.tsx` | File selection, preview, apply, source/record browsing and paginated history |
| `frontend/src/api/client.ts` | Authenticated requests and VIMS TypeScript types |
| `tests/test_vims.py` | Transaction, identity, validation, history and authorization coverage |

## APIs

| Method and path | Access / result |
|---|---|
| `GET /api/vims/schema` | All authenticated roles; exchange JSON Schema |
| `GET /api/vims/example` | All authenticated roles; fictional sample download |
| `POST /api/vims/preview` | Administrator; body is the export document; returns plan and `base_revision` |
| `POST /api/vims/import` | Administrator; body `{ "batch": <document>, "expected_revision": <base_revision> }` |
| `GET /api/vims/sources` | Source revisions and most recent successful export timestamps |
| `GET /api/vims/records/{kind}?source=...&limit=100&offset=0` | `departments`, `vehicles`, `drivers`, `assignments`, `duty_slips`; optional source filter |
| `GET /api/vims/runs?limit=50&offset=0` | Paginated successful/failed apply attempts, newest first |
| `GET /api/vims/runs/{id}` | Attempt details and field changes |

Conflicts return 409; malformed contracts return 422; oversized bodies return 413. The normal authentication middleware returns 401/403 for missing credentials or prohibited writes. Read access follows the existing four-role policy; department-level scoping remains 9.17 work.

## Docker commands

After source changes, rebuild and start the application; backend startup applies the migration:

```powershell
docker compose up -d --build --wait backend frontend
docker compose exec -T backend python -m backend.database_report
```

Preview the packaged fictional sample without importing it:

```powershell
docker compose exec -T backend python -m backend.vims_sync /app/backend/fixtures/vims_sample.json
```

For an actual offline export, place it under the mounted `data/` directory, for example `data/vims/incoming.json`:

```powershell
docker compose exec -T backend python -m backend.vims_sync /app/data/vims/incoming.json
docker compose exec -T backend python -m backend.vims_sync /app/data/vims/incoming.json --apply
```

CLI imports use actor `system:vims-offline-cli`; access is controlled by host/Docker administration. The CLI re-previews before applying and returns a nonzero exit code on validation/conflict errors. An operator can schedule this command against externally supplied exports; no scheduler, external connector or automatic source polling is installed by this milestone. Replace export files atomically so scheduled readers do not see incomplete documents.

## Boundaries and next work

Validation on 7 October 2026: 74 backend tests passed against a disposable PostgreSQL schema, including 17 VIMS tests; frontend TypeScript/Vite build passed. Docker services were activated, the migration applied with existing table counts preserved, and `alembic check` found no pending operations. Live authenticated preview and frontend delivery/proxy checks passed. The sample was not imported into the live registry. Browser-driven interaction testing was not performed.

Imported vehicles feed the existing plate registry and area/hour checks. [Module 9.9](09-09-duty-slip-verification.md) now evaluates duty/assignment records at capture time after source coverage is confirmed, with officer review for destination/purpose questions. Importing a duty slip alone does not mark a detection lawful. Assignment risk sensitivity remains locally configured. Officer names in imported authorization records are source data, not platform user accounts or cryptographic approval verification.

Duty outcomes now feed 9.7 and 9.10. Next, populate a unified vehicle profile for 9.6. Verification attributes provide storage foundations for 9.4; no appearance model or plate-swap classifier is added.
