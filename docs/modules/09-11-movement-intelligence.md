# 9.11 Movement Intelligence Engine

The Digital Twin orders three evidence types by observation time:

- **Registry-linked sighting:** an existing sighting with a foreign key to the vehicle. The status and camera are shown as recorded.
- **Checkpoint crossing:** a crossing on a live-camera track anchored by a manually accepted plate recognition whose detection produced a sighting for this vehicle. Crossings on a track reached through a directly confirmed cross-camera link are labelled separately.
- **Confirmed camera link:** an administrator-confirmed pair of reviewed live-camera plate reads. The link records the two cameras, tracks, reviewed plate and confirming administrator. It is an association for review, not automatic physical identity.

The trail uses vehicle foreign keys, reviewed recognition track IDs and confirmed link keys. Captured plate text alone does not attach a crossing to a vehicle. A link with a conflicting registry vehicle association is excluded. Department officers see sightings and reviewed-track crossings for their own department; cross-camera links and their crossings are shown to administrators and auditors because the camera/track tables are not department bound. Recorded-video track timestamps are processing times, so they are excluded from track-based movement associations.

## API and UI

`GET /api/vehicles/{vehicle_id}/movement-trail` accepts `from`, `to`, `limit` (1-100) and `offset` (0-10000). Date filters require timezone offsets. The response contains `total`, `items`, `alerts`, `alert_total`, and association semantics. Missing or out-of-department vehicles return 404. The **Vehicle Digital Twin** page shows this trail and its reviewable findings using the profile's history date filters. The trail paginates by 20; alerts are calculated for the requested date window. `POST /api/vehicles/{vehicle_id}/movement-alerts/{alert_key}/review` lets an authorized officer or administrator confirm or dismiss a current finding with a note. Reviews are persisted and audited. Auditors can read but cannot review.

## Finding rules and logical flow

An administrator first creates an approved route under **Geofences**. Its department and optional vehicle, approval timestamp, validity interval, weekdays, ordered camera IDs or areas, optional GPS corridor, and assignment/duty requirements define applicability. Policies approved after a sighting cannot be used to judge that past sighting. An observation outside the configured approval dates enters compliance review unless the administrator explicitly enabled date enforcement. Missing verified assignment or active duty remains review-required.

The movement engine requires a reviewed vehicle-linked sighting, or a vetted directly confirmed camera association, before comparing observations. It can raise a review-only `ROUTE_DEVIATION` for an unexpected area, outside-corridor point, or unexpected checkpoint; `UNAUTHORIZED_VISIT` for a GPS point inside a matching restricted polygon; `BOUNDARY_CROSSING` for a connected track leaving the approved corridor; and `ABNORMAL_SEQUENCE` for a reversed approved checkpoint order. These findings do not automatically create a challan or prove misuse. Review status survives refresh; changing a policy revision makes an old finding stale for new reviews.

## Manual check

1. Sign in at `http://localhost:15173` as administrator. Open a vehicle's Digital Twin. Check that existing registry-linked sightings appear in observation-time order, with no inferred checkpoints for historical plate-only data.
2. On Live Camera, capture a consenting test plate with a stable track and a configured checkpoint crossing. Manually accept the ANPR review and check that the crossing appears in the same vehicle's movement trail. An unreviewed or unrelated track must not appear.
3. Capture and review the same test plate on a second camera, then confirm the camera link as administrator. Check that the link and any crossing on the second track appear with an administrator-confirmed label.
4. Sign in as a department officer. Only that department's vehicle should be visible. The trail should not reveal cross-camera links or crossings on linked tracks from other cameras.
5. Filter by dates and inspect the API directly. A timezone-free date, invalid page size, unauthenticated request or missing vehicle should be rejected.

6. As administrator, create a department route with two ordered camera IDs and a corridor; set an active window. Capture and accept a test plate for a vehicle in that department. Check a normal in-window event, then a reviewed event at an unexpected camera/area or outside the corridor. Only the latter should appear as a reviewable finding. Repeat with an unreviewed plate and confirm no route finding appears.
7. Add a restricted zone around a test GPS point. A reviewed sighting inside it should produce `UNAUTHORIZED_VISIT`; an exempt plate or missing GPS should not prove a visit. Inspect the officer's confirm/dismiss action, audit trail and persistence after refresh. Edit the route and verify an older key cannot be newly reviewed under the revised policy.

## Remaining work

Tracking, GPS and checkpoint counts need evaluation on labelled multi-vehicle footage. Camera-to-department binding and institutional route approval are needed before operational use. Findings are computed when a profile is read; there is no push delivery, predictive feed, automatic identity or automatic challan creation.
