# 9.9 Duty Slip Verification

Implemented 7 October 2026. Accepted live-camera plates and manually accepted ANPR results now use imported assignments and duty slips at their original capture time. Decisions, supporting source revision, selected assignment/slip and rule explanations are persisted with the sighting and evidence.

## How to use it

1. Import your department/vehicle/driver/assignment/duty records through **VIMS**. The existing sample is a fictional format example; use an actual plate matching the application's ANPR format for camera testing (for example `AJK123`).
2. In **VIMS → Duty verification → Confirm complete source coverage**, an Administrator selects the source revision, covered period and maximum permitted export age. Confirm only if the assignment/duty records are complete for that interval. Partial offline batches do not prove that a missing slip is a violation.
3. Use **Check a plate and capture time** to inspect a decision without creating an observation. Times entered in the browser are converted from the browser's local timezone into offset-aware API timestamps.
4. Accepted detections automatically run duty checks. The Spotted Vehicles modal, Evidence cards and VIMS duty observation list display the saved decision. Registered vehicles without usable source data require duty review; independent confirmed area/hour violations remain violations.
5. Administrator or Supervisory Officer can resolve pending destination/purpose questions using supporting evidence and a required explanation. The final decision updates the sighting, risk assessment/task and linked evidence transactionally. The original decision is retained in `duty_reviews` and an audit event identifies the authenticated reviewer. Transport Officer and Auditor can read duty decisions but cannot submit final duty reviews.

## Decision rules

| Situation | Duty result |
|---|---|
| No linked VIMS source, unconfirmed revision, uncovered capture time, stale export, or only exports after capture | REVIEW; absence is not proof of unauthorized activity |
| No ACTIVE assignment covering capture time, within confirmed source coverage | FAIL: `ASSIGNMENT_MISMATCH` |
| Multiple matching assignments or source relationship inconsistency | REVIEW |
| No ACTIVE slip covering capture time, including cancelled or outside-period slips | FAIL: `NO_VALID_DUTY_SLIP` |
| Multiple matching active slips | REVIEW; the engine does not choose one arbitrarily |
| Camera-area label is outside the slip's approved areas | FAIL: `UNAUTHORIZED_DESTINATION` |
| Camera-area label is inside the approved areas | Area check PASS; exact destination and actual trip purpose still need evidence |
| Officer confirms destination/purpose match | Pending rule becomes PASS |
| Officer confirms destination/purpose mismatch | Destination maps to `UNAUTHORIZED_DESTINATION`; inconsistent purpose maps to `NO_VALID_DUTY_SLIP` |

Periods are **start-inclusive and end-exclusive** (`start <= capture < end`). All comparison times are converted to UTC. Recurring registry hour checks remain a separate policy. The engine does not infer purpose from a nonempty text field or turn GPS coordinates into a destination label. Approved destinations and purposes are displayed for officer comparison; automatic geocoded destination matching remains future work.

The source snapshot is reconstructed from successful VIMS import changes with `exported_at <= capture_time`. Later cancellations or edits do not rewrite an earlier source snapshot. Freshness means the interval between the selected export and capture, limited by the administrator's policy (1–720 hours; default 72). A new successful source revision invalidates its completeness confirmation until reviewed again. These are as-of-export records, not a claim that institutional approval/cancellation effective timestamps are available.

Coverage is an administrative attestation for imported data. Live institutional VIMS integration remains outstanding. Existing saved decisions are not automatically rescored after imports or coverage changes. Observations blocked by unavailable source data retain that explanation; their destination/purpose rules cannot be bypassed with a human match response. Retrospective source corrections and repeated/appealed duty reviews require a future reprocessing workflow.

## Compliance, risk and evidence

`merge_duty` combines duty outcomes with the existing area/hour/geofence decision. A duty failure or an independently confirmed base violation produces `VIOLATION`. Otherwise unresolved base/duty checks produce `REVIEW_REQUIRED`. A fully resolved lawful base and matching duty become `LAWFUL`. Unregistered plates retain the existing `UNREGISTERED` behavior.

The implementation uses existing risk-policy criteria, so existing policy versions require no rewrite. Overlapping route/destination failures still contribute the maximum route weight once. Time validity and purpose mismatches map to the existing duty criterion. Original risk/compliance snapshots are retained before an officer review replaces the current effective assessment; a qualifying review creates or reopens the officer risk task. It does not issue a formal challan or send external notifications. Review updates do not retroactively recalculate every later event's recurrence score.

Migration `0003_duty_verification` adds `duty_coverage` and `duty_reviews`. Source revision and completeness-window metadata are captured in each duty result. The existing sighting/evidence JSON payloads carry the selected records and explanations, so later source edits do not alter saved observations. Existing records are preserved; records captured before this milestone have no fabricated duty decision.

## Code and APIs

| File | Purpose |
|---|---|
| `backend/duty_verification.py` | Coverage/review schemas, period matching, pure rule evaluation and compliance merge |
| `backend/duty_store.py` | Historical source lookup, coverage confirmation, observation queries, transactional officer reviews |
| `backend/duty_api.py` | API routes and Administrator/Supervisory role dependencies |
| `backend/main.py` | Live and manual ANPR integration; passes capture time to persistence |
| `backend/storage.py` | Rechecks source state inside the save transaction and persists duty snapshots |
| `backend/db_models.py`, `migrations/versions/0003_duty_verification.py` | Relational coverage/review records |
| `frontend/src/components/DutyManagement.tsx` | Coverage form, read-only lookup, observation queue, review controls |
| `frontend/src/components/DutyVerificationPanel.tsx` | Shared saved-decision display in VIMS, Spotted and Evidence |
| `tests/test_duty_verification.py` | Time boundaries, coverage, history, rule/risk behavior, roles and endpoint workflows |

| Method and path | Purpose / access |
|---|---|
| `GET /api/duty/coverage` | Source revisions and coverage confirmations; all authenticated roles |
| `PUT /api/duty/coverage/{source}` | Confirm complete source revision/window; Administrator |
| `GET /api/duty/check?plate=...&observed_at=...&camera_area=...` | Non-persisting lookup; offset-aware time required; all authenticated roles |
| `GET /api/duty/observations?pending=true&limit=100&offset=0` | Saved duty results, optionally limited to unresolved results |
| `GET /api/duty/observations/{id}` | Current sighting and original/reviewed snapshots, when reviewed |
| `POST /api/duty/observations/{id}/review` | Final destination/purpose conclusions; Administrator or Supervisory Officer |

Coverage body: `expected_revision`, `valid_from`, `valid_until`, optional `max_age_hours`. Review body: `destination` and `purpose` (`MATCH`, `MISMATCH`, `UNRESOLVED`) plus `notes` (10–2000 characters). All pending reviewable questions must be resolved in a final submission. Repeated reviews and source-revision conflicts return 409. Missing observations/sources return 404; malformed inputs return 422.

```powershell
docker compose up -d --build --wait backend frontend
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
docker compose exec -T backend alembic check
```

Scope assessment: 9.9 receives **80%** (lookup, validity and period checks implemented; destination and purpose/context receive partial credit because automated contextual matching and authoritative institutional integration are incomplete). The new assignment/duty contributions raise 9.7 to **50%**, with verification/integrity and full assignment/date policy still outstanding.

Validation: **93 backend tests passed against isolated PostgreSQL**, including 19 duty tests; TypeScript/Vite build passed. Live migration/schema checks, read-only API smoke checks and frontend proxy/module delivery passed. Existing live table counts were preserved. Detector inference was stubbed in endpoint tests; no AI accuracy or browser-driven visual validation is claimed.
