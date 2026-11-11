# Module 9.16: Reports and audit

Implemented with the first access-control phase on 10 October 2026.

## Reports

The **Reports** screen generates daily, weekly and monthly summaries and exports
JSON, CSV or PDF. Dates use Asia/Karachi. A selected date chooses its containing
period; weeks run Monday through Sunday. Generation is on demand, not scheduled.

Reports contain fleet size, detection/sighting counts, violations, lawful and
review-required observations, tasks, risk distribution, daily trends, departmental
compliance rates/rankings and formal issuance totals. Department access is applied
before aggregation. Administrators and auditors have platform-wide report access.

Cases are counted by original issuance time even if subsequently cancelled; the
cancelled count is reported separately. Issued face value is not payment revenue.
Lawful percentage is lawful sightings divided by all sightings, including those
requiring review. Departments without sightings have no percentage/rank.
This measures observed compliance, not trip utilization.

`GET /api/reports/compliance?period=monthly&anchor=2026-10-10&format=pdf`
accepts `daily|weekly|monthly`, an optional department name and `json|csv|pdf`.
CSV text is protected against spreadsheet formula interpretation. PDF text is
escaped before rendering. Authentication errors are not downloaded as report files.

## Audit

The **Audit** screen supports actor, action and date filters and pagination.
Administrators and auditors see all entries; supervisors see their department's
entries. Transport Officers cannot browse the log.

`GET /api/audit?actor=officer@example.test&limit=50&offset=0`

HTTP access, denied attempts, successful/failed login and notification outcomes are
recorded. ORM changes to accounts, registry data, assignments, duties, evidence,
recognition, sightings, geofences, tasks and challans create audit entries in the same
database transaction. Existing detailed risk, duty and challan events remain.
Evidence/ANPR reviewer identity comes from authentication, not caller input.
Failed transactions roll back their change logs.

Explicit field allowlists exclude password hashes, tokens, request bodies, provider
credentials and image bytes. Password resets record only that the password changed.
Relevant review changes retain old/new values. Access logs store HTTP method/path/status
without token-bearing query strings.

Application guards and PostgreSQL UPDATE/DELETE triggers make audit entries
append-only through normal operations. A database owner can still alter/drop triggers
or tables; this is not external tamper-proof storage. Legacy audit rows without a
department remain administrator/auditor-only.

## Source and verification

- `backend/governance_api.py`: accounts, reports, periods and audit API.
- `backend/audit.py`: transactional hooks and access outcomes.
- `backend/access.py`: department query criteria.
- `frontend/src/pages/GovernancePages.tsx`: Users, Reports and Audit screens.
- `tests/test_department_access.py`: HTTP isolation, exports, transfers, sessions,
  audit rollback/immutability, concurrent requests and WebSocket revocation.

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
```

Tests use an isolated PostgreSQL schema and temporary files. No external notifications
are sent. Browser visual testing is not part of the automated suite.

### Verified locally on 10 October 2026

- All 133 backend tests passed against isolated PostgreSQL.
- TypeScript compilation and the Vite production build passed.
- Migration `0005_department_access` applied; `alembic check` detected no drift.
- Existing operational record counts were preserved, including 106 vehicles and 85 evidence records.
- Live login, JSON/CSV/PDF reports, role restrictions and the frontend API proxy passed
  using `python tests/smoke_governance.py` inside the backend container.
- The unassigned transport demo account sees zero vehicles until an administrator
  assigns its department in **User access**. Administrator/auditor reports see 106.
- Local frontend: `http://localhost:15173`. No external notifications were sent.

## Remaining work

Scheduled delivery, external audit retention, a durable notification outbox, recipient
acknowledgments, trip utilization and mixed-department case reassignment remain separate
work. Request access logging follows the response; it is not atomic with every
configuration file or external-provider action.
