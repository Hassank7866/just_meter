# 9.4 Vehicle Verification Engine

## Implemented flow

When a new government sighting is saved, the system records a verification snapshot linked to its vehicle and sighting IDs. It copies registered type, make, model and color only when an associated VIMS export existed by capture time. A later export is not used to judge an older observation. The YOLO vehicle label is the only automatic observed attribute. It compares the four supported coarse classes (car, bus, truck, motorcycle); unsupported or missing labels yield `UNKNOWN`, not a mismatch.

The Digital Twin shows each comparison. An officer can enter visually observed make, model and color with notes, then confirm or dismiss a mismatch. Confirmation requires at least one comparable differing attribute and creates a separate `HIGH_REVIEW` verification risk item in the Risk panel. The action is persisted and audited. This does not change the legal compliance decision, create a violation or issue a challan. A plate-swap conclusion is not inferred from one attribute mismatch.

## API and storage

- `GET /api/vehicles/{vehicle_id}/verifications`
- `POST /api/vehicles/{vehicle_id}/verifications/{verification_id}/review`
- `GET /api/vehicle-verification/risk-queue`
- PostgreSQL table `vehicle_verifications`, migration `0009_vehicle_verification`

Vehicle and department access follows the same scoped registry rules as the Digital Twin. Auditors have read access; administrators and assigned officers can review. One review is allowed per verification record.

## Manual check

1. Import or link a test VIMS vehicle with a valid exported time and trusted type, make, model and color. Confirm its attributes in the Digital Twin.
2. Capture a consenting test plate; manually accept the ANPR result if needed. Open that vehicle's Digital Twin and inspect the new verification. A supported type difference should be `REVIEW_REQUIRED`; matching type should be `CONSISTENT`; missing or later source context should be `INSUFFICIENT_DATA`.
3. Enter observed make, model and color from the archived frame or direct inspection, with a note of at least ten characters. Confirm a real mismatch and check the Risk panel for the `HIGH_REVIEW` item. Refresh both screens and inspect Audit. Try reviewing the same item twice; the second request should be rejected.
4. Sign in as an officer from another department and verify the vehicle, verification and risk item are unavailable. An auditor can read but cannot submit a review.

## Remaining work

Make, model and color are officer observations; there is no trained appearance classifier or representative labelled accuracy evaluation. The coarse YOLO class does not prove vehicle identity. Current VIMS payloads are used only when their latest export precedes capture; a later revision makes the historical expected attributes unavailable in this increment. Vehicle crop presentation, multi-frame consistency and validated plate-swap detection remain future work.
