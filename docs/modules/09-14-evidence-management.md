# Module 9.14 — Evidence Management

## Status

**Substantial implementation: 80% of the full scope.** See [current status](implementation-status.md) and [study guide](../fyp-implementation-study-guide.md).

The module creates a unified evidence record for every plate recognition, preserves the full camera frame and plate crop, calculates SHA-256 hashes, detects file modification, supports officer review, links qualifying violations/challans, and exports a portable evidence package.

## Scope coverage

| Requirement | Implementation |
|---|---|
| Detection archive | Full frame stored once per detection event |
| Plate evidence | Individual ANPR plate crop |
| OCR metadata | Plate text, confidence, recognition ID |
| Camera metadata | Camera ID, area, timestamp, frame dimensions, GPS |
| Record links | Detection, ANPR, violation, and challan ID fields |
| Integrity preservation | SHA-256 hashes and on-demand verification |
| Officer review | Separate review state, reviewer, timestamp, and notes |
| Retrieval | Search/filter API and Evidence dashboard |
| Regulatory export | ZIP containing images and JSON manifest |

## Evidence lifecycle

- `review_status`: `CAPTURED`, `UNDER_REVIEW`, or `VERIFIED`.
- `case_status`: `UNASSIGNED`, `ATTACHED_TO_VIOLATION`, or `ATTACHED_TO_CHALLAN`.

Only accepted detections of registered government vehicles that violate authorized-area or duty-schedule rules are recorded as violations and linked to evidence. Unknown/private vehicles and lawful detections are not automatically attached to violations. When the fourth qualifying violation produces a challan, the challan ID is synchronized to evidence for its associated violations. Review updates do not change case associations.

## Integrity model

At capture time, the backend calculates SHA-256 hashes for:

1. The archived full-frame image.
2. The plate-crop image.

The verification endpoint recalculates both hashes and compares them with the capture-time values. A missing or modified file produces `FAILED`. The application does not expose an evidence replacement or deletion endpoint.

## Stored metadata

- Evidence, detection-event, and recognition IDs.
- Timestamp, camera ID, and camera area.
- Plate number and OCR confidence.
- Vehicle type and department when known.
- Full-frame and crop paths, sizes, and hashes.
- Frame width and height.
- Latitude and longitude.
- Separate review, case-association, and integrity statuses.
- Related violation and challan IDs.
- Reviewer, review timestamp, and notes.

Evidence metadata is stored in PostgreSQL `evidence`; `data/evidence_records.csv` is a retained one-time import source. Images remain under mounted `data/snapshots/evidence/` and `data/snapshots/plates/`. Back up both the database and image directory.

## Backend components

| File | Responsibility |
|---|---|
| `backend/storage.py` | Archiving, hashing, searching, integrity verification, and review updates |
| `backend/main.py` | Evidence creation integration and REST/download endpoints |
| `backend/models.py` | Evidence review request validation |
| `backend/config.py` | Evidence record and image paths |

## API endpoints

```http
GET   /api/evidence
GET   /api/evidence/{evidence_id}
POST  /api/evidence/{evidence_id}/verify
PATCH /api/evidence/{evidence_id}
GET   /api/evidence/{evidence_id}/download
```

List parameters:

- `query` searches evidence, detection, recognition, plate, camera, area, and department fields.
- `status` filters by lifecycle status.
- `limit` supports 1–1,000 records.

Review example:

```json
{
  "review_status": "UNDER_REVIEW",
  "reviewer": "Supervisory Officer",
  "notes": "Officer review started"
}
```

`POST /api/evidence/{evidence_id}/verify` only checks file hashes and reports integrity; it does not change review state. `PATCH /api/evidence/{evidence_id}` changes `review_status` to `UNDER_REVIEW` or `VERIFIED`. The case links are assigned by the violation/challan workflow and are not editable through review.

## Download package

The download endpoint returns `Evidence_{evidence_id}.zip` containing:

```text
manifest.json
images/<full-frame>.jpg
images/<plate-crop>.jpg
```

The manifest includes the complete evidence metadata and a fresh integrity-verification result.

## Dashboard workflow

The **Evidence** tab provides:

- Lifecycle filters.
- Search by evidence ID, plate, camera, area, or department.
- Full-frame and plate-crop previews.
- Capture metadata, file sizes, and SHA-256 value.
- On-demand integrity verification.
- Separate Verify Integrity, Review, and Complete Review actions.
- Independent review-state and case-association filters and badges.
- Separate violation and challan links.
- ZIP package download.

## Demonstration procedure

1. Capture a plate using the laptop or mobile camera.
2. Open the Evidence tab.
3. Locate the new evidence using its plate or camera ID.
4. Show the full frame and plate crop.
5. Press Verify Integrity and show the hash result without changing review state.
6. Press Review to open review controls and set `UNDER_REVIEW`.
7. Add notes and press Complete Review to set `VERIFIED`.
8. Download the evidence package.
9. Open `manifest.json` to show metadata and hashes.
10. For a violating vehicle, show its violation and challan relationships when available.

## Tests

`tests/test_evidence_module.py` covers:

- Full-frame and plate-crop archival.
- SHA-256 generation.
- Successful integrity verification.
- Automatic violation linking.
- Detection of modified evidence.
- Independent review and case-status persistence.
- Review updates preserving violation/challan associations.

Run the complete suite:

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
```

## Prototype limitations

- Evidence metadata now uses PostgreSQL; SHA-256 checks image files but review fields remain mutable without append-only history.
- Images use local mounted storage rather than private MinIO/object storage.
- The snapshot route is authenticated. Auditor has broad read access; department-level scoping is still missing.
- SHA-256 detects modification but is not a blockchain or external timestamp authority.
- Retention schedules and automatic archival policies are not implemented.
