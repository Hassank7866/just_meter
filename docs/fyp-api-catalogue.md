# FYP API catalogue and code map

**Checked against all route decorators in [`backend/main.py`](../backend/main.py) on 6 October 2026.** Base URL inside Docker is `http://backend:8000`; from the host it is `http://localhost:8000`. The React client uses the Vite proxy at `http://localhost:5173/api/...`. Interactive schema is at `http://localhost:8000/docs`. Routes are assigned to the module they serve; shared routes appear in more than one module conceptually. For purpose, limits and missing functionality see the [study guide](fyp-implementation-study-guide.md).

**Authentication:** `POST /api/auth/login` accepts `{"email":"...","password":"..."}` and returns `{"success":true,"token":"...","user":{...}}`. Protected REST calls send `Authorization: Bearer <token>`. `GET /health`, `GET /camera-areas` and the camera landing pages are public; `/api/*` except login, `/camera/frame`, `/detections`, `/government-vehicles-spotted` and `/snapshots/*` are protected by [`enforce_api_authentication`](../backend/main.py). The live WebSocket requires a short-lived `live_feed` token in its query string. The mobile upload uses a short-lived `camera_upload` token. See [`auth.py`](../backend/auth.py) and [RBAC details](modules/09-17-authentication-and-rbac.md).

For a safe, read-only Swagger/API demonstration from PowerShell after Docker starts:

```powershell
$fypLogin = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/auth/login -ContentType application/json -Body '{"email":"admin@justmeter.gov","password":"admin123"}'
$fypHeaders = @{ Authorization = "Bearer $($fypLogin.token)" }
Invoke-RestMethod -Uri http://localhost:8000/api/stats -Headers $fypHeaders
Invoke-RestMethod -Uri 'http://localhost:8000/api/dashboard?start_date=2026-10-01&end_date=2026-10-06' -Headers $fypHeaders
```

The seeded password works only if the account has not since been changed; the default date example is the 6 October 2026 review window. Keep the token in a local shell variable and do not paste it into slides or screenshots.

## Startup, registry and dashboard

| Method and path | Function and purpose | Associated module / UI |
|---|---|
| `GET /` | `phone_camera`: mobile/laptop scanner landing page | 9.1; [phone page](../phone/camera.html) |
| `GET /portal`, `GET /admin` | `admin_portal`: serve built frontend if available, with scanner fallback | UI entry |
| `GET /health` | `health`: DB connectivity check | Docker operation |
| `GET /camera-areas` | `camera_areas`: allowed area names | 9.1, 9.7, 9.8 |
| `POST /api/auth/login` | `admin_login`: PostgreSQL user/password check and JWT | 9.17; Login page |
| `GET /api/authorized-vehicles?query=&area=` | `list_authorized_vehicles`: list/filter active local registry | 9.5 support, 9.6, 9.7; Fleet |
| `POST /api/authorized-vehicles` | `create_authorized_vehicle`: create registry row; Admin | 9.5 support; Fleet |
| `PUT /api/authorized-vehicles/{plate_number}` | `update_authorized_vehicle`: edit and preserve identity on plate correction; Admin | 9.5 support; Fleet |
| `DELETE /api/authorized-vehicles/{plate_number}` | `delete_authorized_vehicle`: soft-deactivate local registry row; Admin | 9.5 support; Fleet |
| `GET /api/stats` | `get_stats`: unfiltered registry/sighting/violation/escalation totals | 9.13, 9.16; Navbar |
| `GET /api/dashboard?start_date=&end_date=&department=` | `executive_dashboard`: range/department summaries, daily counts, risk and alerts | 9.13; Overview |

Registry create/update body fields are `plate_number`, `vehicle_id`, `department`, `authorized_areas` (pipe-separated names), `duty_schedule` (`24/7` or `HH:MM-HH:MM`), `risk_context` (`""`, `STANDARD`, `SENSITIVE`, `CRITICAL`), notes and optional officer contact fields. Definitions: [`ApprovedVehicleCreate` / `ApprovedVehicleUpdate`](../backend/models.py); implementation: [`storage.py`](../backend/storage.py). `/api/dashboard` defaults to the past 30 Asia/Karachi calendar days and rejects ranges over 366 days. Current registry count and historic capture-time department activity have different meanings.

## Cameras, detection, ANPR and live feed

| Method and path | Function and purpose | Associated module / UI |
|---|---|---|
| `POST /api/camera/session-token` | `create_mobile_camera_session`: issue 20-minute upload-scoped token | 9.1, 9.17; mobile scanner |
| `POST /api/live-camera/session-token` | `create_live_feed_session`: issue 20-minute WebSocket-scoped token | 9.1, 9.17; Live Camera |
| `POST /camera/frame` | `receive_frame`: multipart image → YOLO + FastALPR → event, recognition, compliance/risk/evidence as applicable | 9.1, 9.3, 9.7, 9.8, 9.10, 9.14 |
| `POST /api/camera/analyze` | `analyze_camera_frame`: laptop/web app wrapper around the same frame path | 9.1, 9.3; Live Camera |
| `POST /api/camera/analyze-video` | `analyze_recorded_video`: sample video frames and persist vehicle events | 9.1; Live Camera |
| `GET /api/vehicle-detection-events?limit=` | `vehicle_detection_events`: recent frame event metadata | 9.1, 9.18 |
| `GET /api/anpr/recognitions?status=&limit=` | `plate_recognitions`: OCR archive/review queue | 9.3, 9.18; ANPR Review |
| `PATCH /api/anpr/recognitions/{recognition_id}` | `review_plate_recognition`: accept corrected text or reject; acceptance may create sighting/risk/evidence links | 9.3, 9.7, 9.10, 9.18 |
| `GET /api/live-camera/latest` | `get_latest_live_frame`: latest in-memory preview, if available | 9.1; Live Camera |
| `WS /ws/live-camera?token=...` | `websocket_live_camera`: real-time frame/event stream for authenticated viewers | 9.1; Live Camera |

Frame POST multipart fields: `file` (JPEG/PNG/WebP), `camera_area`, optional `camera_id`, `frame_number`, `latitude`, `longitude`, `location_accuracy_m`. `/camera/frame` requires the area; `/api/camera/analyze` defaults to `Mzd. Division`. The result includes boxes, OCR readings, counts, a preview and any compliance/evidence details. Video POST accepts a video file, area/ID, `sample_every_n_frames` (default 15) and `max_analyzed_frames` (default 60). It stores vehicle frame events and **does not presently persist video plate readings as ANPR records**.

ANPR PATCH body: `{"status":"ACCEPTED","corrected_text":"AJK123","reviewer":"...","notes":"..."}` or `{"status":"REJECTED",...}`. A correction must fit the prototype plate grammar. The original archived frame is required for acceptance. Review results cannot be re-reviewed. `GET /api/anpr/recognitions` status may be `REVIEW_REQUIRED`, `ACCEPTED` or `REJECTED`.

## Geofences, sightings and compliance results

| Method and path | Function and purpose | Associated module / UI |
|---|---|---|
| `GET /api/geofences` | `list_geofences`: zone records | 9.8; Zones |
| `POST /api/geofences` | `create_geofence`: validate/save polygon; Admin | 9.8; Zones |
| `PUT /api/geofences/{zone_id}` | `update_geofence`: edit polygon/plate filter; Admin | 9.8; Zones |
| `DELETE /api/geofences/{zone_id}` | `delete_geofence`: remove zone; Admin | 9.8; Zones |
| `GET /api/government-vehicles-spotted?limit=` | `government_vehicle_api_history`: matching government sightings and stored compliance/risk snapshots | 9.6, 9.7, 9.8, 9.10; Spotted |
| `GET /government-vehicles-spotted?limit=` | `government_vehicle_history`: protected legacy-format history | Same data, older route |
| `GET /detections?limit=` | `detection_history`: protected generic accepted-plate captures | 9.1, 9.3, 9.16; older route |

Zone body: `name`, `camera_area`, optional `authorized_plates` list and `polygon` of at least three `{latitude,longitude}` points. GPS evaluation happens during frame processing. There is **no** `/api/compliance/evaluate` or standalone geofence-check route. Results are fields in sightings/frame responses. Details: [`geofencing.py`](../backend/geofencing.py), [`compliance_engine.py`](../backend/compliance_engine.py).

## Risk and officer review

| Method and path | Function and purpose | Associated module / UI |
|---|---|---|
| `GET /api/risk/policy` | `get_risk_policy`: current version and complete config | 9.10; Risk panel |
| `PUT /api/risk/policy` | `update_risk_policy`: Admin creates the next immutable version using `expected_version` | 9.10; Risk panel |
| `GET /api/risk/tasks?status=OPEN&limit=200` | `get_risk_tasks`: score-ordered internal officer queue; `ACKNOWLEDGED` or `ALL` also supported | 9.10, 9.13; Risk panel/Overview |
| `PATCH /api/risk/tasks/{task_id}/acknowledge` | `acknowledge_risk_task`: record receipt; assigned officer role or Admin | 9.10, 9.13 |

Risk policy PUT body: `{"expected_version":1,"config":{...}}`; first GET current config and modify a copied value. Validation is in [`RiskPolicyConfig`](../backend/risk_engine.py); stale versions return conflict. There is no endpoint to force scores on all historical cases. New accepted government sightings are scored in [`DetectionStore.save`](../backend/storage.py). The task queue is internal, and task acknowledgment does not approve a challan.

## Evidence and enforcement

| Method and path | Function and purpose | Associated module / UI |
|---|---|---|
| `GET /api/evidence?query=&status=&review_status=&case_status=&limit=` | `evidence_records`: search/filter archive | 9.14; Evidence |
| `GET /api/evidence/{evidence_id}` | `evidence_detail`: one metadata record | 9.14 |
| `POST /api/evidence/{evidence_id}/verify` | `verify_evidence_integrity`: rehash frame/crop and report match/failure | 9.14 |
| `PATCH /api/evidence/{evidence_id}` | `review_evidence_record`: `UNDER_REVIEW` or `VERIFIED`, reviewer/notes | 9.14 |
| `GET /api/evidence/{evidence_id}/download` | `download_evidence_package`: ZIP of images + JSON manifest | 9.14 |
| `GET /api/violations-summary?query=&stage=` | `get_violations_summary`: stable-ID warning/challan eligibility; counts do not imply issuance | 9.15, 9.16; Violations |
| `GET /api/challan/{plate_number}` | Compatibility read of latest persisted issued/upheld case | 9.15 |
| `GET /api/challan/pdf/{plate_number}` | Compatibility read of immutable issued PDF; no evidence writes | 9.15 |
| `GET /api/challans?status=&vehicle_id=&limit=&offset=` | Paginated case register/archive | 9.15; Challans |
| `POST /api/challans` | `{vehicle_id}` creates/opens latest eligible draft | 9.15 |
| `GET /api/challans/{id}` | Case, approval/current snapshots, version, fingerprint and action history | 9.15 |
| `POST /api/challans/{id}/actions` | Versioned amendment, approval, rejection, reopening, issuance, appeal, uphold or cancellation | 9.15 |
| `GET /api/challans/{id}/pdf` | Original issued document, including cancelled/appealed archive | 9.15 |
| `POST /api/send-notification` | `dispatch_violation_notification`: officer-triggered email/WhatsApp notice/link | 9.15 and notification objective |
| `/snapshots/{path}` | Authenticated static image route, mounted by FastAPI | 9.14 and ANPR UI |

Evidence review body: `{"review_status":"UNDER_REVIEW","reviewer":"...","notes":"..."}` or `VERIFIED` after review starts. Hash verification and officer review are different actions. `/api/violations-summary` supports `stage=WARNING` or `CHALLAN`; that filter represents count-based eligibility. Persisted issuance is in `/api/challans`. All four roles may read issued PDFs; creating/changing/sending cases requires an authorized officer. See [module 9.15](modules/09-15-digital-challan.md) for transition roles, expected versions and approval fingerprints.

`POST /api/send-notification` body uses [`ViolationNotificationRequest`](../backend/models.py): `plate_number`, `channel` (`email`, `whatsapp`, `whatsapp_direct`), recipient email/phone and `message_type` (`warning`/`challan`). A challan additionally requires an explicit issued/upheld `challan_id` reference; amounts/counts/PDF bytes come from the saved case and client overrides cannot change them. Pending appeals/cancellations block dispatch. Calling this route may contact an external recipient.

## External notification configuration and diagnostics

| Method and path | Function and purpose | Who may change it |
|---|---|---|
| `GET /api/whatsapp-gateway/status` | `get_whatsapp_gateway_status_endpoint`: local Web bridge status | Read roles |
| `POST /api/whatsapp-gateway/logout` | `logout_whatsapp_gateway_endpoint`: disconnect bridge | Admin |
| `POST /api/whatsapp-gateway/pair-code` | `request_whatsapp_pairing_code_endpoint`: request pairing code | Admin |
| `GET /api/settings/whatsapp` | `get_meta_whatsapp_settings_endpoint`: masked Meta config/status | Read roles |
| `POST /api/settings/whatsapp` | `update_meta_whatsapp_settings_endpoint`: save Meta config | Admin |
| `POST /api/settings/whatsapp/test` | `test_meta_whatsapp_endpoint`: actually send diagnostic message | Admin |
| `GET /api/settings/smtp` | `get_smtp_settings_endpoint`: masked SMTP status | Read roles |
| `POST /api/settings/smtp` | `update_smtp_settings_endpoint`: save SMTP config | Admin |
| `POST /api/settings/smtp/test` | `test_smtp_endpoint`: actually send diagnostic email | Admin |

These are supporting integration APIs, not VIMS or the complete reporting module. Settings persistence currently uses `.env`/environment configuration, while core operational records are in PostgreSQL. The bridge is an optional Docker service with its own session storage. Examine [mailer](../backend/mailer.py), [Meta client](../backend/whatsapp_meta.py), [bridge client](../backend/whatsapp_bridge.py) and [notification route](../backend/main.py) when asked.

## No API exists yet for these scoped engines

There are **no module-specific routes** for 9.2 tracking, 9.4 physical vehicle verification, 9.11 movement intelligence, 9.12 prediction or full 9.18 model monitoring. There is no full 9.16 scheduled report/audit export API. Persisted case actions are documented in [9.15](modules/09-15-digital-challan.md); VIMS and duty routes are documented in [9.5](modules/09-05-vims-synchronization.md) and [9.9](modules/09-09-duty-slip-verification.md).

## Vehicle Digital Twin (9.6)

Routes are implemented in [`digital_twin_api.py`](../backend/digital_twin_api.py), registered in `main.py`, and aggregate existing records through [`DigitalTwinStore`](../backend/digital_twin.py). All four existing officer roles have authenticated read access.

| Method and path | Function and purpose |
|---|---|
| `GET /api/vehicles/digital-twins?query=&limit=30&offset=0` | `vehicles` / `twin_vehicles`: search active and archived registry identities |
| `GET /api/vehicles/digital-twins/resolve` | `resolve` / `twin_reference_id`: exactly one current `plate`, saved `sighting_key` or `evidence_key` resolves to the stable vehicle ID |
| `GET /api/vehicles/{vehicle_id}/digital-twin` | `by_id` / `vehicle_digital_twin`: complete live read model |
| `GET /api/vehicles/{vehicle_id}/movement-trail` | `movement_trail` / `vehicle_movement_trail`: paged chronological registry sightings, reviewed-track checkpoint crossings and confirmed camera links |
| `GET /api/vehicles/by-plate/{plate}/digital-twin` | `by_plate`: normalize current plate and retrieve the same profile |

Profile query parameters: `as_of` (source/duty context time), `camera_area` (optional check context), `from`/`to` (inclusive timeline bounds), `history_limit` (1–100, default 30), and `offset`. All supplied dates require timezone offsets. Registry and summary remain current/all-time; `as_of` does not pretend to reconstruct mutable review/risk state. See [module 9.6](modules/09-06-vehicle-digital-twin.md) for exact semantics and response fields.

## Frontend/API location pattern for code questions

The user action starts in a page under [`frontend/src/pages`](../frontend/src/pages/), uses an API helper in [`client.ts`](../frontend/src/api/client.ts), enters the FastAPI route in [`main.py`](../backend/main.py), then calls a domain module such as [`anpr.py`](../backend/anpr.py), [`compliance_engine.py`](../backend/compliance_engine.py), [`risk_engine.py`](../backend/risk_engine.py), [`geofencing.py`](../backend/geofencing.py) or [`dashboard.py`](../backend/dashboard.py). Storage methods in [`storage.py`](../backend/storage.py) and [`db_records.py`](../backend/db_records.py) persist/query SQLAlchemy models from [`db_models.py`](../backend/db_models.py). The PostgreSQL schema is versioned by [Alembic](../migrations/versions/).
