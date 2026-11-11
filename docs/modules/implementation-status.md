# Module Implementation Status

**11 November 2026 review:** The scored requirement groups sum to **64/90 (71.1%)**. The earlier 65/90 headline was an arithmetic error; the module assessments below are unchanged. See [9.4](09-04-vehicle-verification.md) for the last implementation milestone.

**Reviewed: 11 November 2026 (Asia/Karachi). Estimated implementation: 71.1% of scoped module functionality.**

**Current milestone:** New government sightings carry a conservative vehicle verification snapshot. Officers can review captured attributes and confirmed mismatches enter a separate risk queue. Approved routes and reviewable movement findings remain in place. Automatic appearance classification, cross-camera identity, independent appellant submissions, payment integration and institutional validation remain incomplete. The [implementation study guide](../fyp-implementation-study-guide.md) contains historical code orientation; its older percentages should not be used as current status.

This assessment compares the current working tree, including uncommitted and untracked files, with `D:/fyp/GovTrack_ScopeDocument.pdf` (26 PDF pages). Section 9 defines 18 modules on PDF pages 13-17. Sections 7, 10, 13, and 14 provide additional requirements and constraints. The document uses both Just Meter AJK and GovTrack AJK names. Its contents were treated as assessment criteria, not instructions to execute.

The project has a substantial detection-to-compliance demonstration, including initial tracking, offline VIMS synchronization, reviewed movement findings, assisted vehicle verification and a formal enforcement workflow. Predictive analytics and institutional validation remain largely outstanding. This percentage measures functional coverage, not effort spent, AI accuracy, production readiness, or a supervisor-approved grade.

## Scoring method

The scope supplies no numerical weights. This review weights each of the 18 modules equally and divides each into five requirement groups, listed in the scorecard below. A group earns **1 point** for meaningful implementation, **0.5 points** for a limited implementation or supporting foundation with material gaps, and **0 points** when no meaningful implementation was found.

Each module has a maximum of 5 points. Overall coverage is **64 / 90 x 100 = 71.1%**. Module percentages equal earned points divided by 5. These are review estimates based on code and available tests, not measured end-to-end acceptance results. Equal weighting makes the calculation reproducible but does not imply equal development effort. Requirements repeated across scope sections are assessed through their corresponding modules rather than counted again. This review inspected current source and existing test cases; it did not rerun a field-camera or institutional acceptance test.

The previous tracker marked 9.1, 9.3, and 9.14 “Completed for prototype.” Those labels described narrower demonstration workflows. Their full scope gaps are now explicit.

## Module assessment

| Module | Name | Status | Coverage | Implemented behavior | Main remaining scope work |
|---|---|---|---:|---|---|
| 9.1 | Vehicle Detection Engine | Substantial implementation | 90% | YOLO11 boxes, four vehicle classes, multiple detections, per-frame counts, configured checkpoint crossings, live frames and sampled video | Validated physical-vehicle counts, recorded-video ANPR handoff and representative model evaluation |
| 9.2 | Vehicle Tracking Engine | Partial | 50% | Persistent per-camera track IDs, observation history, configured line crossings, reviewed plate candidates and confirmed cross-camera links | Validated multi-object tracking, automatic cross-camera reidentification and route reconstruction |
| 9.3 | ANPR Engine | Substantial implementation | 80% | Plate detection, generic OCR, confidence/format filtering, correction suggestions, crops, manual acceptance into compliance | Localization constrained to vehicle regions, adapted OCR and representative accuracy evaluation, recorded-video integration |
| 9.4 | Vehicle Verification Engine | Partial | 40% | Trusted VIMS attribute snapshot, conservative detected-type comparison, officer-assisted make/model/color comparison and confirmed mismatch risk queue | Trained appearance verification, labelled accuracy evaluation, full historical source replay and validated plate-swap detection |
| 9.5 | VIMS Synchronization Engine | Partial | 50% | Offline exchange contract, atomic department/vehicle/driver/assignment/duty-slip imports, source identities, preview, conflicts, history and CLI | Institutional schema mapping and acceptance, live API connector, periodic database synchronization and read-only view adapters |
| 9.6 | Vehicle Digital Twin Module | Substantial implementation | 90% | Stable-ID profile API/UI, current registry, historical source/duty context, linked capture/compliance/evidence/risk/task history, movement trail, search, pagination and refresh | Unlinked/no-plate detection identity and complete immutable historical state remain unavailable |
| 9.7 | Compliance Rules Engine | Partial | 70% | Recurring hours, approved route dates, areas, polygons, capture-time assignment/duty checks and audited duty resolution | Full observed-officer checks, automated contextual destination checks and vehicle integrity |
| 9.8 | Geofencing Engine | Substantial implementation | 90% | Configurable authorized/restricted polygons, plate and department filters, assignment/duty gates, approved route policies and compliance outcomes | GPS accuracy buffers, road-network routes, camera ownership and map UI |
| 9.9 | Duty Slip Verification Engine | Substantial implementation | 80% | Historical source lookup, coverage/freshness checks, assignment and active-slip validity, periods, area checks, snapshots, officer destination/purpose resolution and risk integration | Automatic geocoded destination/context matching, authoritative institutional validation and retrospective source-correction workflow |
| 9.10 | Risk Assessment Engine | Substantial implementation | 90% | Versioned configurable policies, bounded history, severity/context factors, route-overlap suppression, persistent assessments and prioritized officer review tasks | Authoritative temporal assignment/VIMS context and additional compliance/verification inputs; external delivery and formal challan approval remain separate module dependencies |
| 9.11 | Movement Intelligence Engine | Substantial implementation | 80% | Vehicle-specific trail, approved route comparison, restricted visits, corridor boundary crossings, checkpoint order findings and audited human reviews | Real-footage accuracy, automatic identity, proactive alerts and predictive analytics feed |
| 9.12 | Predictive Misuse Analytics Engine | Not started | 0% | Repeat counts in risk scoring are retrospective | Historical patterns, escalating profiles, movement anomalies, predictive flags and proactive intervention |
| 9.13 | Executive Dashboard Module | Substantial implementation | 90% | Dedicated overview, date/department filters, current fleet and historical department activity, daily trends, risk distribution, officer alert acknowledgment and count-derived enforcement stages | Duty/trip-based departmental utilization; formal issuance statistics depend on 9.15 |
| 9.14 | Evidence Management Module | Substantial implementation | 80% | Frames/crops, OCR/camera metadata, case links, review, SHA-256 checks, ZIP export | Images for all detection events, including no-plate and recorded-video events; immutable record history |
| 9.15 | Digital Challan Module | Substantial implementation | 90% | Automatic stable-ID drafts, independent approval, verified evidence/hash checks, immutable issued PDFs, officer-recorded appeals, cancellation, action/delivery history and case UI | Independent appellant submission and attachments, institutional process/fine validation; payment collection and resilient external dispatch remain absent |
| 9.16 | Reporting and Audit Module | Substantial implementation | 90% | On-demand daily/weekly/monthly JSON, CSV and PDF reports; department filters; authenticated reports/audit screens; transactional changes, access outcomes and append-only protections | Scheduled delivery, external audit retention, durable notification outbox and recipient acknowledgments |
| 9.17 | Authentication and RBAC Module | Substantial implementation | 90% | Four role types, department query isolation, capture-time ownership, account lifecycle, session revocation and checks across APIs, images, exports and WebSockets | MFA, delegated departments, PostgreSQL row-level security, camera-to-department binding and device-specific sessions |
| 9.18 | AI Model Monitoring Module | Partial | 30% | Stored confidence/model metadata, thresholds and low-confidence ANPR review | Confidence distributions, ground-truth OCR accuracy, drift, multi-model monitoring and broader human review |

### Requirement group scorecard

Each row lists all five groups. Numbers in parentheses are earned points, subject to the validation limits below.

| Module | Five requirement groups and credits | Earned / 5 |
|---|---|---:|
| 9.1 | Live/recorded ingestion (1); localization (1); classification/multiple detections (1); checkpoint counting (1); tracking/ANPR handoff (0.5) | 4.5 |
| 9.2 | Consecutive-frame identities (1); multi-object tracker (0.5); cross-camera identities (0.5); movement reconstruction (0); downstream correlation (0.5) | 2.5 |
| 9.3 | Vehicle-region plate localization (0.5); adapted OCR (0.5); confidence/quality filtering (1); correction/validation (1); crop archiving (1) | 4 |
| 9.4 | Registered attribute storage foundation (0.5); coarse type verification (0.5); assisted make/model/color verification (0.5); plate-swap/mismatch detection (0); confirmed mismatch risk queue (0.5) | 2 |
| 9.5 | Offline vehicle exchange (0.5); department exchange (0.5); driver exchange (0.5); duty exchange (0.5); offline adapter/CLI, pending institutional connectors (0.5) | 2.5 |
| 9.6 | Registry profile (1); linked detection history aggregation (0.5); compliance history aggregation (1); VIMS/duty aggregation (1); unified updated profile (1) | 4.5 |
| 9.7 | Hours/approved dates (1); area/geofence checks (1); assignment existence/context checks (1); integrated duty-slip checks (0.5); vehicle integrity checks (0) | 3.5 |
| 9.8 | Configurable polygons (1); location evaluation (1); compliance outcomes (1); vehicle-assignment configuration (0.5); department/duty/approved-route configuration (1) | 4.5 |
| 9.9 | Active duty lookup (1); validity check (1); area/assisted destination match (0.5); approved period (1); assisted purpose/context and violation output (0.5) | 4 |
| 9.10 | Four classifications (1); category/severity scoring (1); occurrence frequency (1); assignment/historical-profile context (0.5); risk-driven enforcement routing (1) | 4.5 |
| 9.11 | Cross-checkpoint sequences (1); route deviations (1); unauthorized visits (0.5); boundary crossings (1); abnormal patterns and analytics feed (0.5) | 4 |
| 9.12 | Historical patterns (0); recurring behavior identification (0); escalating profiles (0); movement anomalies (0); predictive intervention flags (0) | 0 |
| 9.13 | Compliance summaries (1); departmental usage (0.5); active alert management (1); challan-stage statistics (1); executive risk/trend interface (1) | 4.5 |
| 9.14 | All-event image archive (0.5); OCR/camera metadata (1); case links (1); review/retrieval/export (1); immutable evidence records (0.5) | 4 |
| 9.15 | Automatic linked drafts (1); designated review/approval (1); formal issuance (1); officer-recorded appeals (0.5); status/archive/action history (1) | 4.5 |
| 9.16 | Periodic reports (1); operational/compliance analysis (1); structured reports (1); system-wide audit (1); administrative/enforcement history (0.5) | 4.5 |
| 9.17 | Token authentication (1); session management (1); four-role separation (1); authorization across interfaces (1); department scoping (0.5) | 4.5 |
| 9.18 | Confidence-distribution monitoring (0.5); OCR accuracy (0); drift detection (0); multi-model monitoring (0); low-confidence human review (1) | 1.5 |
| **Total** | **18 modules, 90 possible points** | **64 / 90** |

## Implementation evidence

| Modules | Source evidence and existing documentation |
|---|---|
| 9.1-9.3 | [Detector](../../backend/detectors.py), [frame/video/review APIs](../../backend/main.py), [tracking and line geometry](../../backend/tracking.py), [checkpoint/link storage](../../backend/tracking_store.py), [plate text rules](../../backend/anpr.py), [Live Camera](../../frontend/src/pages/LiveCameraPage.tsx), [tracking controls](../../frontend/src/components/TrackingPanel.tsx), [ANPR Review](../../frontend/src/pages/ANPRReviewPage.tsx), [9.1 details](09-01-vehicle-detection-engine.md), [9.2 details](09-02-vehicle-tracking.md), [9.3 details](09-03-anpr-engine.md) |
| 9.11 | [Movement read model](../../backend/movement.py), [API](../../backend/movement_api.py), [profile panel](../../frontend/src/components/MovementTrailPanel.tsx), [tests](../../tests/test_movement.py), [module guide](09-11-movement-intelligence.md) |
| 9.5-9.6 | [Database registry and summaries](../../backend/storage.py), [registry schemas](../../backend/models.py), [Authorized Vehicles](../../frontend/src/pages/AuthorizedVehiclesPage.tsx), [Spotted Vehicles](../../frontend/src/pages/SpottedVehiclesPage.tsx) |
| 9.6 | [Read model](../../backend/digital_twin.py), [API](../../backend/digital_twin_api.py), [profile screen](../../frontend/src/pages/VehicleProfilePage.tsx), [tests](../../tests/test_digital_twin.py), [module guide](09-06-vehicle-digital-twin.md) |
| 9.4 | [Comparison and review store](../../backend/vehicle_verification.py), [API](../../backend/verification_api.py), [Digital Twin panel](../../frontend/src/components/VehicleVerificationPanel.tsx), [tests](../../tests/test_vehicle_verification.py), [module guide](09-04-vehicle-verification.md) |
| 9.4-9.5 foundation | [VIMS contract](../../backend/vims_schema.py), [transactional sync](../../backend/vims_store.py), [API](../../backend/vims_api.py), [migration](../../migrations/versions/0002_vims.py), [VIMS screen](../../frontend/src/pages/VimsPage.tsx), [module guide](09-05-vims-synchronization.md) |
| 9.7/9.9 integration | [Duty rules](../../backend/duty_verification.py), [lookup/review persistence](../../backend/duty_store.py), [API](../../backend/duty_api.py), [duty controls](../../frontend/src/components/DutyManagement.tsx), [module guide](09-09-duty-slip-verification.md) |
| 9.7-9.10 | [Risk engine](../../backend/risk_engine.py), [risk persistence/routing](../../backend/risk_store.py), [database/risk guide](../database-and-risk.md), [Compliance/risk](../../backend/compliance_engine.py), [geofence rules](../../backend/geofencing.py), [zone APIs](../../backend/main.py), [Geofences](../../frontend/src/pages/GeofencesPage.tsx), [compliance/risk details](09-07-compliance-and-risk.md), [geofencing details](09-08-geofencing.md) |
| 9.13 | [Dashboard aggregation](../../backend/dashboard.py), [Executive overview](../../frontend/src/pages/ExecutiveDashboardPage.tsx), [dashboard tests](../../tests/test_dashboard.py), [module details](09-13-executive-dashboard.md) |
| 9.14-9.15 | [Evidence/challan/notification APIs](../../backend/main.py), [case persistence and PDFs](../../backend/challan_store.py), [Evidence](../../frontend/src/pages/EvidencePage.tsx), [Violations](../../frontend/src/pages/ViolationsPage.tsx), [Challans](../../frontend/src/pages/ChallansPage.tsx), [evidence details](09-14-evidence-management.md) |
| 9.16-9.17 | [Department query rules](../../backend/access.py), [accounts/reports/audit API](../../backend/governance_api.py), [audit hooks](../../backend/audit.py), [migration](../../migrations/versions/0005_department_access.py), [User access/Reports/Audit screens](../../frontend/src/pages/GovernancePages.tsx), [RBAC details](09-17-authentication-and-rbac.md), [report details](09-16-reporting-and-audit.md) |
| 9.18 | [Model thresholds](../../backend/config.py), [ANPR confidence review](../../backend/anpr.py), [ANPR details](09-03-anpr-engine.md) |
| 9.15 | [Case store](../../backend/challan_store.py), [API](../../backend/challan_api.py), [issued PDF](../../backend/challan_pdf.py), [migration](../../migrations/versions/0004_challans.py), [register UI](../../frontend/src/pages/ChallansPage.tsx), [tests](../../tests/test_challan_workflow.py), [module guide](09-15-digital-challan.md) |

“No implementation found” conclusions were based on backend modules/routes, frontend pages, data schemas, tests and repository searches. UI labels, generic data fields and proposed documentation were not treated as completed engines.

## Coverage snapshot

- **Full scoped module completion:** 0 of 18.
- **Substantial implementation (80% or above):** 12 modules (9.1, 9.3, 9.6, 9.8-9.11, 9.13-9.17).
- **Partial, including foundation only:** 5 modules (9.2, 9.4, 9.5, 9.7, 9.18).
- **Not started:** 1 module (9.12).
- **Some implementation:** 17 / 18 = 94.4%. This measures breadth, not completion.

## Additional scope findings

These qualify the module estimate; they are not additional weighted modules.

1. **Notifications are partial.** SMTP, Meta WhatsApp, a WhatsApp bridge, templates and officer-triggered sending exist. Challan delivery attempts now record sent/link-created/failed outcomes, and appeals suspend dispatch. Automatic delivery, recipient acknowledgment, a durable outbox and broader warning-delivery audit remain absent. Section 7.1's automated warning objective remains incomplete.
2. **Challan issuance is now persisted.** Fourth-and-later observations create drafts. Independent approval, verified evidence, an issuance action and archived PDF are required before official-case sending. Summaries now use stable vehicle identity and label count-based eligibility separately. Appeals are recorded by officers; institutional acceptance, direct appellant submission and payment collection remain outstanding.
3. **Tracking is an initial per-camera implementation.** Consecutive detections receive persistent track IDs and observations. A configured line can count a track once per checkpoint revision. Different-camera links need reviewed accepted plate reads and administrator confirmation. Recorded-video timestamps are processing times, and sampled-video totals still sum detections per frame. Track stability on representative occlusion footage and physical vehicle counting accuracy have not been established.
4. **Evidence is not archived for every detection event.** Live-frame image evidence is created inside the plate-recognition loop; no-plate frames receive event metadata only. Recorded-video analysis stores vehicle events and discards plate output. SHA-256 detects image changes, but database evidence metadata and latest review fields remain mutable without append-only history.
5. **Access control has remaining gaps.** Middleware protects operational APIs, image routes and WebSockets. Users, sessions and account administration are persisted in PostgreSQL, with department query isolation for supported records and reports. MFA, database row-level security, camera-to-department binding and delegated access remain absent.
6. **Model training/evaluation remains outstanding.** Section 10 proposes adapted detection/plate/OCR/verification models and four datasets. Code uses general `yolo11n.pt` and `cct-xs-v2-global-model`. Corresponding training pipelines, curated datasets, ground-truth accuracy reports and verification classifiers were not found. Business-logic tests do not establish AI accuracy or throughput.
7. **PostgreSQL migration is implemented and deployed in Docker.** Alembic, transactional legacy import, persistent users, relational event/evidence links and versioned risk records are in place. Original CSV/JSON files and image paths are retained. Audit covers application changes and access outcomes with append-only protections. External audit retention and a validated encrypted deployment remain outstanding. No model accuracy or institutional pilot acceptance was established by this work.

Section 7.2 exclusions were respected: no penalty was added for citywide infrastructure, onboard GPS tracking hardware, face/driver identity recognition, national registry integration, a field-officer mobile app, blockchain, gate control or production SLA/internet-scale deployment. Browser-supplied GPS can support polygon checks without excluded onboard trackers.

## Database/risk milestone validation: 6 October 2026

The database/risk milestone increased this rubric from **31/90 (34.4%) to 33/90 (36.7%)**: 9.10 gained 1.5 points and 9.17 gained 0.5. PostgreSQL is a shared foundation rather than an additional section-9 module, so it was not awarded a separate arbitrary percentage.

**49 backend tests passed in Docker against an isolated PostgreSQL schema.** The frontend TypeScript/Vite production build passed. Backend and frontend images were rebuilt and activated; PostgreSQL and the backend report healthy.

| Test group | Passed | Coverage |
|---|---:|---|
| Existing eight backend suites | 32 | ANPR, authentication, escalation, compliance, geofencing, evidence, manual review and detection persistence |
| `tests/test_database_and_risk.py` | 14 | Import repeatability/rollback, relationships, plate correction, recurrence windows, policy versions, context, routing, transaction failure and restart-safe duplicates |
| `tests/test_risk_api.py` | 3 | Policy authorization/validation/version conflicts, protected legacy routes and database geofence CRUD |
| **Total** | **49** | **Passed** |

The live migration imported **105 vehicles, 294 frame events, 70 recognitions, 18 detections, 3 government sightings, 50 evidence records and 1 geofence**, preserving source IDs and image paths. Seven import ledger entries track source counts/checksums. A backend restart retained all counts; the repeat import reported all seven sources already imported with unchanged checksums. Live login, registry, evidence image, geofence, statistics, risk and dashboard HTTP checks passed. Four demo users and the initial risk policy were seeded. Historical scores were preserved; new-policy risk tasks are created for subsequent qualifying detections rather than fabricated for old records.

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
docker compose run --rm --no-deps frontend npm run build
docker compose exec -T backend python -m backend.database_report
```

The test runner uses a disposable PostgreSQL schema and temporary images. These tests establish application/migration behavior, not model inference accuracy. No external notifications were sent. See [database and risk documentation](../database-and-risk.md) for schema, operational commands and remaining dependencies.

## Executive dashboard milestone: 6 October 2026

Module 9.13 increased from **2.5/5 (50%) to 4.5/5 (90%)**, bringing overall coverage from **33/90 (36.7%) to 35/90 (38.9%)**. Department activity earns partial usage credit because actual duty/trip utilization needs additional data. The existing challan-statistics credit represents count-derived stages; the dashboard explicitly calls these review eligibility rather than formal issuance. No additional credit is assigned to 9.15 or 9.16 for this dashboard work.

The default Overview tab now provides date/department filters, current fleet and historical activity, risk distribution, daily counts and trends, and role-controlled acknowledgment of prioritized officer alerts. Historical department attribution and vehicle identity survive registry changes. The API uses existing PostgreSQL tables and requires no migration. See [module 9.13](09-13-executive-dashboard.md) for definitions, dependencies and commands.

**57 backend tests passed against isolated PostgreSQL**, including **8 dashboard tests** for dates, department attribution, missing context, prior-history escalation, alert ordering/limits/permissions, legacy scores and archived/renamed vehicles. The preceding 49 database/risk and existing behavior tests also pass. The frontend TypeScript/Vite production build passed.

The rebuilt Docker services were activated successfully. Live authenticated dashboard, department filtering, full-year aggregation, frontend page/module delivery and frontend API proxy checks passed using the existing records (105 registered vehicles, 18 saved detections, 3 government sightings). No browser-driven visual/interaction test was run.

## VIMS foundation milestone: 7 October 2026

Module 9.5 gains **2.5/5 (50%)** for offline vehicle, department, driver and duty exchange plus the adapter foundation. Each group receives partial credit because the exchange contract has been tested with fixtures rather than an institutional VIMS schema; the three scoped external integration approaches are not all implemented. Module 9.4 gains **0.5/5 (10%)** for imported attribute storage, with no verification model or mismatch decision. Total coverage increases from **35/90 (38.9%) to 38/90 (42.2%)**. Imported duty storage receives no separate 9.9 credit because detection-time verification is still absent.

**74 backend tests passed against isolated PostgreSQL**, including **17 VIMS tests**, and the TypeScript/Vite production build passed. The tests cover read-only previews, entity references, complete-batch rollback, failed-run history, idempotency, source ownership, explicit local adoption, plate changes with historical links, stale previews/exports, assignment overlaps, duty periods, cancellations, registry edit protections, request limits and all four API roles.

Docker backend/frontend images were rebuilt and activated. Migration **0002_vims** is deployed; `alembic check` reports no pending schema operations. Existing counts remained unchanged: 106 vehicles, 17 departments, 394 frame events, 105 recognitions, 36 detections, 6 government sightings and 85 evidence rows. Existing users, geofences, legacy import ledger and risk records were preserved. Live authenticated preview, sample download and frontend proxy/module delivery passed. VIMS tables remain empty until an administrator imports a source; the sample was previewed only. No browser-driven visual/interaction test was run.

See [module 9.5](09-05-vims-synchronization.md) for all APIs, code locations, contract rules and Docker commands. The subsequent duty-verification milestone is described below.

## Duty-verification milestone: 7 October 2026

Module 9.9 gains **4/5 (80%)** and integrated assignment/duty checks add **1 point** to 9.7, which reaches **2.5/5 (50%)**. Overall coverage becomes **43/90 (47.8%)**. Destination and purpose/context retain partial credit because source destination labels lack automatic geocoded matching and purpose needs officer evidence. Coverage confirmation protects against treating an incomplete offline export as proof of missing authorization. No additional risk-module credit is assigned merely for receiving these new criteria.

**93 backend tests passed against isolated PostgreSQL**, including **19 duty-verification tests** and the preceding 74 tests. The frontend TypeScript/Vite build passed. Coverage includes time boundaries, stale/future exports, cancellation history, conflicting slips, source-revision invalidation, persisted snapshots, role checks, risk/route overlap, audited officer resolution, and actual live-upload/manual-ANPR endpoint workflows with detector inference stubbed. These tests do not establish model accuracy.

Docker backend/frontend services are healthy. Migration **0003_duty_verification** is applied and `alembic check` reports no pending operations. Existing counts remained 106 vehicles, 17 departments, 394 frame events, 105 recognitions, 36 detections, 6 government sightings and 85 evidence records; users, geofences, imports and risk records were also preserved. Read-only live login, duty endpoints, missing-source REVIEW behavior, frontend proxy and module delivery passed. No sample records, source coverage attestations or duty reviews were added to the live database. Browser-driven interaction testing was not performed.

See [module 9.9](09-09-duty-slip-verification.md) for APIs, rules, source-coverage setup and the remaining limitations.

## Digital Twin milestone: 8 October 2026

The latest completed milestone is described in [9.6 Vehicle Digital Twin](09-06-vehicle-digital-twin.md). Module 9.6 increases from **2/5 (40%) to 4.5/5 (90%)**, bringing overall coverage from **43/90 (47.8%) to 45.5/90 (50.6%)**. Linked detection history retains half credit because unknown/no-plate identities and movement tracking are unresolved. Other module scores are unchanged.

**103 backend tests passed against isolated PostgreSQL**, including **10 Digital Twin tests**, and the frontend TypeScript/Vite production build passed. New tests cover empty/missing source states, future exports, half-open duty periods, plate correction/archive/history preservation, capture-time department attribution, independent timeline pagination/totals, unrelated-vehicle isolation, direct/recognition evidence relationships, risk/tasks/reviews, live aggregation and authenticated API validation. No browser-driven interaction or visual test was run.

The rebuilt backend/frontend containers are active and the backend is healthy. Live authenticated ID/plate profile requests, historical sighting reference resolution, missing-source REVIEW behavior, frontend proxy and page-module delivery passed; unauthenticated reads return 401. Database counts remained unchanged at 106 vehicles, 17 departments, 394 frame events, 105 recognitions, 36 detections, 6 government sightings and 85 evidence records. All other table counts were unchanged as well. No live sample import, duty confirmation, external notification or new migration was performed.

## Digital Challan milestone

The subsequent Digital Challan milestone increases 9.15 from **1.5/5 (30%) to 4.5/5 (90%)**, bringing overall scope coverage to **48.5/90 (53.9%)**. Appeals receive half credit for the officer-recorded workflow; independent appellant submissions/attachments remain absent. No extra score was assigned to adjacent modules for consuming the case data.

**118 backend tests passed against isolated PostgreSQL**, including **15 new challan workflow tests** and an updated automatic-draft/evidence regression. The final frontend TypeScript/Vite build passed. Coverage includes idempotency, time/identity attribution, independent approval, stale fingerprints/versions, evidence review and tampering, transaction rollback, fixed PDF bytes, appeal/cancellation permissions, legacy-route bypass prevention and mocked notification outcomes. No actual external messages were sent. Browser-driven interaction testing was not performed.

Migration **0004_challans** is applied; `alembic check` reports no pending operations. Backend and database are healthy and the frontend is running. Read-only live checks passed for authenticated/unauthenticated case routes, the frontend proxy and new screen, Digital Twin, and actual issued-case statistics. Existing counts remained 106 vehicles, 6 government sightings, 85 evidence records, 394 frame events, 105 recognitions and 36 detections; other existing table counts were preserved. New case/event tables remain empty until eligible observations or explicit historical draft requests occur. Windows port reservations required changing host mappings: frontend **15173** (`FRONTEND_PORT`), PostgreSQL **15432** (`POSTGRES_PORT`); internal container ports remain 5173 and 5432.

## Vehicle-tracking milestone: 10 October 2026

Module 9.2 advances from **0/5 to 2/5 (40%)**, bringing this rubric to
**56.5/90 (62.8%)**. It adds persistent per-camera track IDs, one-to-one box
association, ordered observations, a plate-to-track reference, a unique-track count
for each recorded upload and administrator-only track APIs. Historical frame events
are preserved without fabricated track IDs. See [module 9.2](09-02-vehicle-tracking.md).

**136 backend tests passed against isolated PostgreSQL**, including three tracking
cases. The final association changes also passed six focused SQLite tests. The
frontend TypeScript/Vite production build passed. Migration `0006_vehicle_tracking`
is active and `alembic check` detected no drift. Existing live counts remained
unchanged, including 106 vehicles, 394 frame events, 105 recognitions, 36
detections, six government sightings and 85 evidence records. The new track tables
are empty until a fresh camera/video observation is processed. Live login/report
checks and track API role checks passed; no external notifications were sent.
Visual camera and labelled-video accuracy evaluation remain manual work.

## Checkpoint and cross-camera tracking milestone: 10 October 2026

Module 9.1 now earns **4.5/5 (90%)** for configured checkpoint counts; 9.2 earns **2.5/5 (50%)** for persistent per-camera tracks, line crossings and confirmed cross-camera links. Overall coverage rises from **56.5/90 (62.8%) to 57.5/90 (63.9%)**. A crossing is saved once per track and checkpoint revision, using the vehicle-box center moving across the configured finite line. Changing a checkpoint creates a new revision. Candidate cross-camera links require the same manually accepted plate on different live cameras, within the configured time window; an administrator must confirm each link. These links do not establish automatic identity or a reliable route.

**143 backend tests passed against an isolated PostgreSQL schema**, including seven new checkpoint, link, permission and synthetic-video tests. The TypeScript/Vite production build passed. Backend and frontend images were rebuilt and activated. A local database backup was taken before migration **0007_checkpoint_links**; `alembic check` reports no pending schema changes. The backend and database are healthy, the governance smoke test passed, and no external notifications were sent. The live database contains 106 vehicles, 424 frame events, 132 recognitions, 9 tracks, 12 observations and 112 evidence records after deployment. Checkpoints, crossings and cross-camera links remain at zero until configured and exercised. Labelled road footage and browser interaction have not yet been evaluated.

To check manually, sign in as administrator at **http://localhost:15173**, open **Live Camera**, enter a distinct camera ID and save a checkpoint line in the tracking panel. Place the line across the expected path of the vehicle-box center, select the travel direction and send a short sequence of frames in which one visible vehicle crosses it. The crossing total should increase once, while the same track can produce later observations without another count. Inspect `/api/checkpoint-crossings?camera_id=YOUR-CAMERA-ID` and `/api/vehicle-tracks` for saved details. Repeat with a recorded clip that has two vehicles or partial occlusion; note whether track IDs remain stable and whether the count matches visible crossings. For cross-camera linking, submit live frames to two camera IDs, manually accept matching plate reads in **ANPR Review**, then inspect the candidate in the tracking panel and confirm it as administrator. Test with an intentionally different plate and a gap beyond the time window; neither should produce a candidate. Use test data only.

## Movement trail milestone: 11 October 2026

The first 9.11 increment earns **0.5/5 (10%)** for a limited cross-checkpoint sequence view, raising estimated overall coverage from **57.5/90 (63.9%) to 58/90 (64.4%)**. It adds `GET /api/vehicles/{vehicle_id}/movement-trail` and a movement section on the Digital Twin page. The trail combines vehicle-FK sightings, checkpoint crossings tied to manually reviewed live tracks, and directly confirmed camera links. Cross-camera links are withheld from department officers pending camera-to-department ownership rules. No route violation or enforcement decision is generated from this trail. See [module 9.11](09-11-movement-intelligence.md) for evidence rules and manual checks.

**148 backend tests passed against an isolated PostgreSQL schema**, including five movement tests for reviewed anchors, confirmed links, conflicting vehicle identities, department isolation, authentication and date validation. The frontend TypeScript/Vite production build passed. Backend and frontend images were activated locally; the backend and database are healthy, `alembic check` reports no pending operations, and the governance smoke check passed. The read-only live movement smoke check returned two saved sightings for a linked vehicle through both the backend and frontend proxy. Existing data counts were preserved: 106 vehicles, 424 frame events, 132 recognitions, 9 tracks, 12 track observations, 6 government sightings and 112 evidence records. No new migration, sample movement write or external notification was made. Browser interaction and labelled-road-footage accuracy remain manual checks.

## Approved routes and movement findings milestone: 11 October 2026

Modules 9.7, 9.8 and 9.11 rise by 1, 1 and 3.5 points respectively. The estimate increases from **58/90 (64.4%) to 63.5/90 (70.6%)**. The route policy includes department and optional vehicle ownership, approval timestamp, dates and weekdays, ordered camera/area sequence, optional GPS corridor and assignment/duty requirements. Authorized and restricted polygons now support department-aware checks. Compliance evaluates approved dates with review as the default for missing context. A route finding requires reviewed identity evidence and is never an automatic challan. Officers can confirm or dismiss findings; actions are persisted and audited. See the module guides for the logical flow and manual checks.

**155 backend tests passed against isolated PostgreSQL**, including seven new route, geofence, compliance, movement and access tests. The final TypeScript/Vite production build passed. A backup was saved as `data/just-meter-before-approved-routes-20261011.dump` before migration `0008_approved_routes`; `alembic check` reports no pending operations. Backend and database are healthy. Read-only governance, movement and route API/proxy smoke checks passed. Live counts remain 106 vehicles, 424 frame events, 132 recognitions, 9 tracks, 12 track observations, 6 government sightings and 112 evidence records. The new route and alert review tables are empty until an administrator configures routes and test sightings qualify. No external notifications were sent. Browser interaction and labelled-road-footage accuracy remain manual checks.

To test manually at **http://localhost:15173**, sign in as administrator, open **Geofences**, create an authorized polygon for a test department and an approved route for a test vehicle. Set a short current validity window, ordered camera IDs and a corridor polygon; optionally require a verified assignment and duty slip. Process a test plate and manually accept the ANPR result so its sighting is linked to that vehicle. In **Digital Twin**, check the movement trail and any route findings. Observe the same plate at an unexpected camera or outside the corridor to produce a reviewable route deviation; move a connected reviewed track from inside to outside the corridor to test a boundary crossing. Add a restricted polygon around a known GPS test point and verify an inside sighting creates an unauthorized visit finding. Reverse the approved checkpoint order to test the sequence rule. Confirm or dismiss a finding as a department officer and refresh; inspect **Audit** for the review. Then revise the route and verify an older finding cannot be newly reviewed under its stale key. An unreviewed plate, missing GPS, missing verified assignment or missing duty must not be treated as proven misuse. Use test data only.

## Vehicle verification milestone: 11 October 2026

Module 9.4 rises from **0.5/5 (10%) to 2/5 (40%)**. The historical milestone text reported **65/90 (72.2%)**, but the current scorecard rows total **64/90 (71.1%)**; the discrepancy was arithmetic, not a newly removed feature. New government sightings store a capture-time attribute snapshot. Supported YOLO type labels are compared with available VIMS attributes; officers can record observed make, model and color with notes. Confirmed mismatches enter a separate high-priority verification review queue. The system does not infer plate swapping or change legal compliance from a mismatch. See [9.4](09-04-vehicle-verification.md) for API behavior, manual checks and limits.

**160 backend tests passed against isolated PostgreSQL** and the frontend TypeScript/Vite build passed. A pre-migration backup was saved as `data/just-meter-before-verification-20261011.dump`; migration `0009_vehicle_verification` is active and `alembic check` reports no drift. Backend and database are healthy. A read-only live verification API/proxy smoke check passed. The new table has zero records because the live database contains no VIMS source and no new government sightings were created for this check. Existing counts remain 106 vehicles, 424 frame events, 132 recognitions, 9 tracks, 6 government sightings and 112 evidence records. No external notifications were sent. Browser interaction and model accuracy remain untested.

## Recommended next implementation sequence

1. **Validate with the AJK departments and VIMS owner.** Confirm the exchange schema, authoritative fields, department names/IDs, duty-slip data and operating rules before importing institutional records (9.5, 9.7, 9.9).
2. **Evaluate vehicle tracking (9.2).** Test per-camera IDs and checkpoint counts against labelled clips, crowded scenes and occlusion; calibrate checkpoint lines and measure false or duplicate counts before operational use.
3. **Validate movement intelligence (9.11).** Agree on approved routes and camera ownership with departments, compare reviewed findings against labelled real footage, then add proactive alert delivery and an analytics feed.
4. **Validate and extend vehicle verification (9.4).** Populate trusted VIMS attributes, label representative imagery, measure type and attribute accuracy, then train and evaluate appearance models before attempting plate-swap detection.
5. **Evaluate and monitor the vision models (9.1, 9.3, 9.18).** Create representative labelled data, report detection/OCR accuracy by conditions, track confidence and drift, and include recorded-video/no-plate evidence in review.
6. **Complete operational workflows (9.13–9.17).** Add scheduled report delivery and acknowledged notification outbox, define case reassignment across departments, improve trip/duty utilization metrics, and validate the challan appeal/payment and retention process with the institution.

This order addresses prerequisites: movement analysis depends on reliable tracking; route decisions depend on approved institutional data; verification and alerts need measured model quality and human review.

## Manual acceptance test

Run the app locally with Docker Desktop. In PowerShell from the project root:

```powershell
docker compose up -d --build
docker compose ps
```

Open the frontend at **http://localhost:15173** (the configured host port), API docs at
**http://localhost:8000/docs**, and check **http://localhost:8000/health**. Use the
existing demo passwords unless they were changed: `admin@justmeter.gov` / `admin123`,
`transport@justmeter.gov` / `transport123`, `supervisor@justmeter.gov` /
`supervisor123`, and `auditor@justmeter.gov` / `auditor123`.

1. **Admin and department setup:** Sign in as admin. Open **User access**, edit the
   transport and supervisor users, assign the same existing department, save, and
   confirm it appears in each account row. Create a temporary officer, verify the
   required department validation, then disable/re-enable it and revoke its sessions.
2. **Fleet and scoping:** Sign in as transport officer. Check Fleet and Spotted counts.
   Return to admin, change the officer to a different department, sign in again and
   confirm the lists and counts change. Try opening a record URL copied from the
   other department; it should be absent or return 404. An unassigned officer should
   see no fleet records.
3. **Evidence and images:** As an assigned officer, open department evidence and
   download a plate crop. The UI/API should not provide full camera frames or raw
   frame events to officers. As admin, verify the full-frame view is available.
4. **Reports:** Generate daily, weekly and monthly reports as admin and assigned
   officer. Compare the selected department totals. Download CSV and PDF and open
   them; verify date range, summary and trend rows. Auditor reports should show the
   platform totals.
5. **Audit:** As admin, change a test user’s department or role, then open **Audit**
   and filter by actor/action/date. Confirm the change appears. Auditor can read the
   history; transport officer receives no audit access.
6. **Session revocation:** Keep the officer logged in in a second browser/private
   window. Revoke that user from admin **User access**. Refresh the officer page; the
   session should expire and require sign-in.
7. **Existing workflows:** As admin, inspect Overview, Authorized Vehicles, VIMS
   preview, Duty, Spotted, Evidence, Risk/Violations, Digital Twin and Challans. Use
   existing records and read-only previews first. For write actions, create a clearly
   identified test record and remove it only through the application workflow. Check
   the related audit/history view after an action.
8. **Camera/ANPR/tracking:** If a camera is available, open **Live Camera**, grant
   browser camera access, scan a consenting test plate and verify the
   recognition/evidence/review chain. Keep a vehicle in view for several frames:
   its box should retain a track suffix and **New tracks** should increase once.
   As admin, save a checkpoint line in the tracking panel and move the vehicle-box
   center across it. Verify **Crossings** increases once for the track; inspect
   `/api/checkpoint-crossings` and `/api/vehicle-tracks`. Upload a short video with
   two vehicles or an occlusion; compare observations, tracks and crossings against
   the footage. Review accepted plate reads from two different live camera IDs and
   confirm a proposed link in the tracking panel. Also submit a test image through
   the mobile scanner. Do not use a real enforcement notice or external notification
   for this acceptance check.
9. **Movement trail:** Open a registry vehicle in **Digital Twin** and inspect the
   new movement section. Existing sightings should appear in time order. A reviewed
   live track with a checkpoint crossing should add a labelled crossing, and an
   administrator-confirmed link should add a separately labelled camera link.
   Use the history date filters and compare against the source observations.
   Sign in as a department officer and check that other departments' vehicles and
   unscoped cross-camera links are absent.
10. **Restart persistence:** Run `docker compose restart backend`, sign in again,
   and confirm test data and review history persist. Check `docker compose ps` for a
   healthy backend and database.

The demo account passwords are for local evaluation. Do not expose this setup publicly
with demo credentials or the local signing secret. Browser camera permissions require
a secure context such as localhost or HTTPS. Model results vary by camera, lighting,
plate style and image quality; a successful workflow check does not establish OCR
accuracy.

## Status definitions

- **Not started:** no meaningful module-specific implementation; incidental inputs do not count as an engine.
- **Partial:** some scoped requirements implemented, with substantial workflow/data/authorization gaps.
- **Substantial implementation:** at least 80% under this rubric, with explicit remaining gaps.
- **Complete against scope:** all scored requirements implemented and intended workflow validated. No module currently meets this definition.
