# Module 9.1 — Vehicle Detection Engine

## Status

**Substantial implementation: 80% of the full scope.** See [current status](implementation-status.md) and [study guide](../fyp-implementation-study-guide.md).

The implementation supports live laptop frames, mobile-camera frames, and sampled recorded-video analysis. It detects supported vehicle classes with YOLO11 and creates persistent frame-level detection events.

## Scope requirements

The scope document requires this module to:

- Ingest live or recorded video.
- Perform frame-level vehicle localization.
- Classify vehicles by type.
- Detect multiple vehicles in a frame.
- Count vehicles at checkpoints.
- Forward detection output to later tracking and ANPR stages.

## Implemented behavior

### Input sources

- Laptop browser camera.
- Mobile browser camera through an HTTPS tunnel.
- Mobile scanner page served by the backend.
- Recorded MP4, AVI, MOV, MKV, and WebM files.
- Direct image/frame upload API.

### Detection

- Ultralytics YOLO11 using `yolo11n.pt`.
- Supported COCO vehicle classes:
  - Car.
  - Motorcycle.
  - Bus.
  - Truck.
- Multiple vehicles per frame.
- Bounding box for every vehicle.
- Vehicle class label.
- Detection confidence.
- Configurable minimum vehicle confidence.

### Frame-level event metadata

Every analyzed frame stores:

- Unique event ID.
- Timestamp.
- Camera/checkpoint ID.
- Camera area.
- Source type: `LIVE_FRAME` or `RECORDED_VIDEO`.
- Source frame number when available.
- Frame width and height.
- Total detected vehicle count.
- Model name and model version.
- Serialized detection labels, confidence values, and bounding boxes.

## Backend components

| File | Responsibility |
|---|---|
| `backend/detectors.py` | Lazy model loading and YOLO vehicle inference |
| `backend/main.py` | Live-frame, web-camera, recorded-video, and history endpoints |
| `backend/storage.py` | Persistent frame-level detection event storage |
| `backend/models.py` | Frame and recorded-video API response schemas |
| `backend/config.py` | Confidence thresholds and event storage path |

## Frontend components

| File | Responsibility |
|---|---|
| `frontend/src/pages/LiveCameraPage.tsx` | Source controls, live feed, overlays, counters, video upload, and mobile pairing |
| `frontend/src/api/client.ts` | Live-frame and recorded-video API contracts |
| `frontend/src/vite-env.d.ts` | Vite environment-variable typing |

## API endpoints

### Analyze a live frame

```http
POST /camera/frame
```

Multipart fields:

| Field | Required | Description |
|---|---|---|
| `file` | Yes | JPEG, PNG, or WebP frame |
| `camera_area` | Yes | Configured operating area |
| `camera_id` | No | Checkpoint/camera identifier |
| `frame_number` | No | Source frame sequence number |
| `latitude` | No | Camera latitude |
| `longitude` | No | Camera longitude |
| `location_accuracy_m` | No | GPS accuracy in metres |

### Analyze a web-camera frame

```http
POST /api/camera/analyze
```

This uses the same processing flow as `/camera/frame` and is called by the dashboard laptop camera.

### Analyze recorded video

```http
POST /api/camera/analyze-video
```

Multipart fields:

| Field | Default | Description |
|---|---:|---|
| `file` | Required | Recorded video |
| `camera_area` | `Mzd. Division` | Simulated checkpoint area |
| `camera_id` | `VIDEO-CAM-001` | Source identifier |
| `sample_every_n_frames` | 15 | Sampling interval |
| `max_analyzed_frames` | 60 | Processing safety limit |

Example response:

```json
{
  "source_type": "RECORDED_VIDEO",
  "camera_id": "CHECKPOINT-01",
  "camera_area": "Mzd. Division",
  "filename": "demo.mp4",
  "frames_read": 300,
  "frames_analyzed": 20,
  "vehicles_detected": 14,
  "events": []
}
```

### Retrieve detection events

```http
GET /api/vehicle-detection-events?limit=100
```

The limit must be between 1 and 1,000.

## Persistence

Frame-level events are stored in PostgreSQL `vehicle_events`. `data/vehicle_detection_events.csv` is a preserved one-time legacy import source. Docker retains database records in the `postgres-data` volume.

## User interface

The Live Camera screen provides one consolidated Camera Source panel:

- Camera/checkpoint identifier field.
- Laptop Camera / Stop Laptop toggle.
- Mobile Camera pairing control.
- Recorded-video upload.
- Visible camera and video errors.
- Session vehicle, plate, and violation counters.
- Vehicle bounding-box and class-label overlays.

The obsolete duplicate Feed Source panel was removed.

## Mobile HTTPS tunnel

The `mobile-tunnel` Docker service forwards the backend scanner through LocalTunnel:

```text
https://just-meter-ajk-fyp-232424.loca.lt/
```

HTTPS is required because mobile browsers restrict camera access on insecure non-localhost origins.

## Tests

Tests are located in:

```text
tests/test_vehicle_detection_module.py
```

Covered behavior:

- Association of a plate bounding box with its containing vehicle.
- Creation of unique frame-level event IDs.
- Persistence of camera metadata.
- Correct per-frame vehicle counts.
- YOLO model metadata.
- Detection JSON round-trip from storage.

Run:

```powershell
docker compose run --rm --no-deps backend python -m backend.test_runner --postgres
```

Current result: **2 tests passed**.

The frontend also passes TypeScript and Vite production compilation:

```powershell
docker compose run --rm --no-deps frontend npm run build
```

## Demonstration procedure

### Live laptop camera

1. Open the dashboard and select Live Camera.
2. Enter `CHECKPOINT-01` as the camera ID.
3. Click Laptop Camera and grant permission.
4. Point the camera at a vehicle image or vehicle.
5. Observe detected vehicle boxes, labels, confidence, and session counts.
6. Click Stop Laptop.
7. Call the event-history endpoint to show the persisted detection event.

### Mobile camera

1. Click Mobile Camera.
2. Open the displayed HTTPS scanner URL on a phone.
3. Select the camera area and start the camera.
4. Point the phone at a vehicle.
5. Observe the synchronized feed on the dashboard.

### Recorded video

1. Set the camera ID to `VIDEO-DEMO-01`.
2. Select Analyze Recorded Video.
3. Upload a supported video.
4. Show analyzed-frame, vehicle-count, and saved-event results.

## Prototype limitations

- The current YOLO11 weights use general COCO vehicle classes and have not yet been fine-tuned on a dedicated AJK government-vehicle dataset.
- Recorded videos are sampled to keep CPU-only demonstrations responsive.
- Frame events use PostgreSQL. Sampled-video results distinguish box observations,
  new per-camera tracks and configured checkpoint crossings. Crossing counts depend
  on the camera line and tracker stability; they have not been validated against
  physical vehicle counts. See [Module 9.2](09-02-vehicle-tracking.md).
- Plate recognition behavior is documented separately under Module 9.3.
