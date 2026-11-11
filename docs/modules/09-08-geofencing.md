# 9.8 Geofencing Engine

## Implemented prototype flow

Administrators configure named authorized or restricted polygon zones in the dashboard. Each zone belongs to one configured camera area and can optionally specify a department and plate list. Authorized coverage can require a verified assignment or active duty slip. In restricted zones, the plate list acts as exemptions. Zone definitions persist as `data/geofences.json` in the backend data volume and can be created, listed, edited, and deleted through `/api/geofences`.

For an approved vehicle, compliance evaluates the GPS point against applicable authorized polygons, including department and required duty context. The point-in-polygon helper uses longitude as x and latitude as y; points on an edge count as inside. A point inside an applicable polygon passes. A point outside every applicable polygon records `OUTSIDE_GEOFENCE`; missing GPS or no matching authorization returns `REVIEW_REQUIRED`. Restricted polygons feed review-only movement findings and do not count as authorized coverage. With no authorized zones configured, the compliance geofence rule is inactive. ANPR accepted during manual review uses the archived capture's original GPS coordinates.

Administrators can also create approved routes in the same screen. A route belongs to a department and optionally one registry vehicle, with validity dates, weekdays, ordered camera IDs/areas and an optional corridor polygon. Its approval time and revision are recorded in PostgreSQL. Route windows support compliance checks; corridor and sequence comparisons support movement findings. See [9.11](09-11-movement-intelligence.md).

## Dashboard setup

Open **Geofences**, choose a camera area, enter one `latitude, longitude` pair per polygon vertex, and save at least three distinct valid coordinates. Optional plate restrictions are comma separated. Camera capture must provide GPS coordinates before a configured zone can produce a pass/fail result.

## API and persistence

- `GET /api/geofences`
- `POST /api/geofences`
- `PUT /api/geofences/{zone_id}`
- `DELETE /api/geofences/{zone_id}`
- `GET /api/approved-routes`, `POST /api/approved-routes`, `PUT /api/approved-routes/{route_id}` (administrator only)
- Persistent file: `data/geofences.json` (mounted data volume)
- Persistent tables: `approved_routes`, `movement_alert_reviews` (migration `0008_approved_routes`)
- Compliance rule identifier: `GPS_GEOFENCE`
- Violation criterion: `OUTSIDE_GEOFENCE`

## Limits

This is point-in-polygon, not road-network routing. It does not account for GPS accuracy, altitude, polygon self-intersection, or map-based drawing. A GPS point at the boundary is considered inside. If authorized coverage exists but none matches a vehicle, the result needs manual review. Route policy administration is role restricted, but routes have not been validated by the institution.

## Demonstration checks

1. Create a zone and reload the dashboard; confirm it remains in the list.
2. Submit a detection with a vehicle authorized for that area and a GPS point inside the polygon; expect `GPS_GEOFENCE: PASS`.
3. Submit a point outside it; expect `VIOLATION`, `OUTSIDE_GEOFENCE`, and a risk factor.
4. Submit missing GPS or a vehicle whose authorized areas have no matching polygon; expect `REVIEW_REQUIRED`.
5. Test a point on a polygon edge; expect it to count as inside.
6. Delete the zone and verify it no longer appears; when the last zone is deleted, polygon enforcement is inactive.
