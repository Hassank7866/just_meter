# 9.13 Executive Dashboard

The **Overview** tab is the default page after login. It reads PostgreSQL through `GET /api/dashboard` and refreshes every 30 seconds. All four existing roles can read it. Alert acknowledgment uses the existing task ownership checks: Administrator or the assigned officer role.

## Implemented

- Date and department filters, defaulting to the last 30 calendar days in Asia/Karachi. Both end dates are inclusive; the maximum range is 366 days.
- Current active fleet totals, distinct observed vehicle identities, government sightings, lawful observations, violations and unassessed/review observations.
- Daily saved plate detections, government sightings and violations, with zero-filled dates, an activity chart and an accessible count table that also shows High/Critical observations.
- Department activity table combining current registered fleet with historical observation counts.
- Violation risk distribution, including explicit pending/unassessed categories. Historical scores without a versioned assessment are identified. Records are never rescored by opening the dashboard.
- Open and acknowledged task counts, the top 20 open tasks ordered by score, and permission-controlled acknowledgment with the existing audit trail. Filters apply to the task's originating sighting date and department, not its acknowledgment date.
- Warning-stage and challan-review-eligible vehicle counts, using all violations through the selected end date for vehicles with violations inside the selection.
- Links to the existing fleet, sightings and enforcement pages. These links open the full operational pages; overview filters are not transferred.

## Metric definitions

Activity is attributed to the **department captured with the sighting**. Registry transfers do not rewrite past attribution. Fleet counts describe the current active registry, so an old department can have sightings but no current registered vehicles. Blank historical departments appear as `Unassigned`.

Distinct observed vehicles use the stable vehicle database ID when available and normalized plate otherwise. Plate corrections and registry archiving preserve linked historical identity. Multiple sightings are not unique trips. Saved plate detections count persisted detection records after acceptance/cooldown; they do not count every YOLO box or unaccepted OCR candidate. A department filter includes only detections linked to a sighting in that department.

Risk distribution counts violations, not distinct vehicles. Lawful and unassessed compliance records do not become Low risk. Existing historical risk levels are retained; different policy versions may contribute to one chart. Open tasks mean acknowledgment is pending; acknowledgment alone does not resolve a violation or issue a challan.

The warning threshold remains 1–3 recorded violations, and challan-review eligibility starts at 4. These are count-derived stages, **not formal issued challans or collected fines**. Prior violations outside the selected start date still contribute to the stage; records after the selected end date do not.

## Scope coverage and remaining work

Estimated **90% (4.5/5)** under the implementation tracker: compliance summaries 1, departmental usage 0.5, active alert management 1, warning/challan-stage statistics 1, executive risk/trend interface 1. Departmental activity is available, but duty utilization, duration, distance and trip-level usage require assignment/duty/tracking data. Formal challan issuance statistics will use module 9.15 when that lifecycle exists. Current access follows the existing platform roles; department-based access restrictions remain a module 9.17 gap. The department selector is a reporting filter, not an authorization boundary.

No database migration is needed: the dashboard reads the existing tables. PostgreSQL analytics use a repeatable-read transaction without acquiring the global write lock. Observation queries are date-bounded; aggregation runs in Python for the pilot dataset. The all-history stage calculation is grouped in SQL. Larger deployments would need profiling and database aggregation/caching.

## Docker validation

```powershell
docker compose build backend frontend
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
docker compose up -d --wait backend frontend
```

Validation on 6 October 2026: **57 backend tests passed against PostgreSQL**, including 8 dashboard tests; the frontend TypeScript/Vite production build passed.

The rebuilt backend/frontend containers were activated and reported healthy. Live authenticated checks verified the default dashboard, department filtering, a full-year range, frontend module delivery and the frontend API proxy. Current records produced 105 registered vehicles, 18 saved detections, 3 government sightings, 2 distinct observed vehicles and 0 open tasks. These checks verify API delivery and aggregation; a browser-driven visual/interaction test was not run.

`tests/test_dashboard.py` covers empty/default results, authentication and invalid filters, Pakistan-day boundaries, zero-filled days, department transfers, missing context, escalation history, queue limits and priority, acknowledgment permissions/idempotency, legacy risk, plate correction and registry archiving. The runner uses a disposable PostgreSQL schema and temporary images.

Source: [aggregation](../../backend/dashboard.py), [API](../../backend/main.py), [page](../../frontend/src/pages/ExecutiveDashboardPage.tsx), [tests](../../tests/test_dashboard.py).
