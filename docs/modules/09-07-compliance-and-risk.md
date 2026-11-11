# Compliance Decisions and Violation Risk

Updated 11 October 2026.

## Status

**9.7 remains partial (70% in the implementation tracker).** Area, duty-hours, polygon, approved-route date and capture-time assignment/duty checks produce explainable decisions. Missing route approval or unverified context leads to manual review. Outside-date observations fail only when an administrator explicitly enables route date enforcement. Observed-officer context, automatic destination matching and vehicle integrity checks remain outstanding.

**9.10 has substantial prototype coverage (90% in the implementation tracker).** Versioned configurable policies, bounded recurrence windows, severity/history/context contributions, overlapping-route suppression, saved explanations and officer review routing are implemented. Assignment context is maintained on the registry; authoritative assignment/VIMS context and additional compliance inputs remain dependencies.

See [Database and risk assessment](../database-and-risk.md) for policy fields, scoring, review tasks, container commands and limitations.

## Decisions

| Outcome | Meaning |
|---|---|
| `LAWFUL` | Configured checks passed |
| `VIOLATION` | Configured checks failed |
| `REVIEW_REQUIRED` | OCR or required policy information needs review |
| `UNREGISTERED` | No government registry match |

Rules retain identifiers, outcomes, reasons and criteria. PostgreSQL stores the original decision snapshot. Accepted manual ANPR review uses the archived capture time; risk history is bounded relative to that time.

## Risk persistence and interface

- `backend/risk_engine.py`: pure scoring and configuration validation.
- `backend/risk_store.py`: policy versions, historical context, assessment persistence and task routing.
- `backend/storage.py`: atomic detection/sighting/risk/task writes and persistent duplicate suppression.
- `frontend/src/components/RiskAssessmentPanel.tsx`: explanation, officer queue, acknowledgment and administrator policy editing.
- Authorized Vehicles provides the assignment risk context field.

A task acknowledgment records receipt, not challan approval. The separate digital challan module handles draft review, approval, issuance and officer-recorded appeals. Movement findings remain human-review items and do not automatically create challans.

## Validation

Run the full suite against a disposable PostgreSQL schema:

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
```

The suite covers scoring, policy versions, permissions, transactional rollback, historical windows, import repeatability, retained relationships and restart-safe duplicate suppression. Model inference accuracy is outside these tests.
