# Module 9.3 — ANPR Engine

## Status

**Substantial implementation: 80% of the full scope.** See [current status](implementation-status.md) and [study guide](../fyp-implementation-study-guide.md).

The module localizes plates, performs OCR, preserves raw results, normalizes and validates plate text, creates correction suggestions, archives plate crops, and routes uncertain results through a human review workflow.

## Scope coverage

| Requirement | Implementation |
|---|---|
| Plate localization | FastALPR plate detector returns plate bounding boxes |
| OCR | FastALPR `cct-xs-v2-global-model` |
| Confidence scoring | OCR character confidence is aggregated and stored |
| Quality filtering | Configurable `MIN_PLATE_CONFIDENCE` threshold |
| OCR normalization | Uppercase alphanumeric normalization |
| OCR correction | Suggestions for common `O/0`, `I/1`, `Z/2`, `S/5`, and `B/8` confusion |
| Plate validation | Prototype pattern of 1–4 letters followed by 1–4 digits |
| Plate image archive | Bounding-box crop saved for every recognition |
| Human oversight | Review queue with accept/correct/reject actions |

## Processing flow

```text
Camera frame
  → plate localization
  → OCR raw text and confidence
  → normalization
  → format validation
  → correction suggestion
  → plate crop archive
  → accepted automatically OR queued for manual review
```

A recognition is automatically accepted only when its confidence meets the configured threshold and its normalized text already matches the prototype plate format. Uncertain values stay out of enforcement until an officer accepts a corrected plate. On acceptance, the backend reloads the original archived frame and capture metadata, runs the compliance and risk engines at the original capture time, saves the resulting sighting, and updates the existing evidence record with any violation/challan link. Rejected readings remain excluded.

## Recognition statuses

- `REVIEW_REQUIRED` — low confidence or invalid format.
- `ACCEPTED` — automatically accepted or visually confirmed by an officer.
- `REJECTED` — determined not to contain a reliable plate result.

## Stored fields

- Recognition ID.
- Parent vehicle-detection event ID.
- Timestamp, camera ID, and camera area.
- Raw, normalized, suggested, and final plate text.
- OCR confidence and format-validity result.
- Review status and reason.
- Plate-crop path and bounding box.
- OCR model name.
- Reviewer, review timestamp, and notes.

Runtime recognition records are stored in PostgreSQL `plate_recognitions`. The CSV is a retained one-time import source. Crops are stored under mounted `data/snapshots/plates/`; preserve both the database volume and images.

## Backend components

| File | Responsibility |
|---|---|
| `backend/anpr.py` | Normalization, validation, correction suggestions, and decision logic |
| `backend/detectors.py` | Plate localization and raw OCR inference |
| `backend/storage.py` | Recognition records, crops, queue retrieval, and review updates |
| `backend/main.py` | Recognition integration and review endpoints |
| `backend/models.py` | ANPR response and review request schemas |

## API endpoints

### List recognition records

```http
GET /api/anpr/recognitions?status=REVIEW_REQUIRED&limit=200
```

Valid filters are `REVIEW_REQUIRED`, `ACCEPTED`, and `REJECTED`. Omitting the status returns all records.

### Review recognition

```http
PATCH /api/anpr/recognitions/{recognition_id}
Content-Type: application/json
```

Accept example:

```json
{
  "corrected_text": "AJK123",
  "status": "ACCEPTED",
  "reviewer": "Transport Officer",
  "notes": "Verified from plate crop"
}
```

Reject example:

```json
{
  "corrected_text": "",
  "status": "REJECTED",
  "reviewer": "Transport Officer",
  "notes": "Plate is unreadable"
}
```

Accepted corrections must pass plate-format validation.

## Dashboard workflow

The dashboard includes an **ANPR Review** navigation tab with:

- Review Required, Accepted, Rejected, and All filters.
- Search by plate, camera, or area.
- Plate-crop preview.
- Raw and normalized OCR text.
- Confidence and review reason.
- Suggested/corrected plate editor.
- Accept and Reject actions.
- Compliance result, risk level, duplicate-cooldown outcome, and evidence case link after acceptance.

## Demonstration procedure

1. Start the laptop or mobile camera.
2. Present a clear plate to demonstrate automatic acceptance.
3. Present a blurred, distant, or partially obscured plate to create a review item.
4. Open **ANPR Review**.
5. Show the crop, raw OCR, confidence, normalization, and reason.
6. Correct the plate text and press Accept, or press Reject.
7. Review the returned compliance decision, risk level, and linked evidence, then switch filters to demonstrate the persisted status and reviewer information.

## Tests

`tests/test_anpr_module.py` covers:

- Text normalization.
- Prototype format validation.
- Common OCR correction suggestions.
- Low-confidence review routing.
- Plate crop creation.
- Review-queue filtering.
- Manual correction and acceptance persistence.

`tests/test_manual_anpr_enforcement.py` covers accepted low-confidence recognition flowing through compliance/risk evaluation and updating its archived evidence relationship.

The complete backend unit suite also covers evidence, detection, compliance/risk scoring, and review-to-enforcement integration.

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
```

## Prototype limitations

- The OCR model is generic and has not yet been fine-tuned on an AJK/Pakistani government-plate dataset.
- The prototype validation expression intentionally supports a broad letters-plus-digits format; a production registry should define plate series by jurisdiction and department.
- Correction logic produces suggestions and deliberately avoids rewriting structurally valid but potentially ambiguous plates.
- Recognition metadata now uses PostgreSQL; image crops remain mounted files.
- Accepted manual reviews require the original archived full frame; if it is missing or unreadable, the API refuses acceptance so that it cannot silently skip compliance evaluation.
- Duplicate captures inside the existing cooldown are not recorded as another violation, including when an officer reviews the plate during that cooldown.
