# Module 9.2: Vehicle tracking

Implemented as a per-camera tracking foundation on 10 October 2026.

## What works

The detection pipeline now assigns a `TRK-...` ID to each supported vehicle box.
Nearby boxes of the same class in subsequent frames share that ID through a
one-to-one association. Each track and observation is stored in PostgreSQL, so the
history survives a backend restart. Live camera frames share an identity within a
short time window. Every recorded-video upload gets its own stream ID, preventing
unrelated uploads from being joined merely because they use the same camera name.

Each frame event retains its box count and includes `new_track_count`. Recorded-video
responses retain `vehicles_detected` as the number of analyzed boxes and add
`unique_vehicles`, the number of tracks started during that upload. The camera screen
shows track suffixes on boxes and counts newly started tracks. A plate read, its
recognition and its evidence record carry the associated track ID when the plate
centre lies inside a vehicle box.

## Checkpoint crossings and camera links

An administrator can configure one line per camera in **Live Camera → Checkpoint
tracking**. Its endpoints are normalized coordinates from 0 to 1, so the same line
applies to frames of different sizes. A crossing is counted when a tracked vehicle's
box centre moves from one side of the finite line to the other. A small dead band
reduces jitter counts. Direction can be both ways, A to B, or B to A. The database
enforces one crossing per track and checkpoint revision. Editing the line increments
its revision and preserves earlier crossings with their original line snapshot.

Live frames include `new_crossing_count` and the crossing track IDs. Recorded-video
results include `checkpoint_crossings` alongside the existing box and track totals.

The **Cross-camera candidates** section compares manually accepted live ANPR reads
from different camera IDs. Candidates require the same normalized plate and a time
gap within 180 minutes by default. An administrator explicitly confirms the match;
the confirmation, reviewer and underlying recognition references persist in
`track_links`. Candidates are suggestions and do not establish vehicle identity on
their own. Recorded-video uploads are excluded because their current timestamps
represent processing time rather than the original capture time.

## API and storage

- `GET /api/vehicle-tracks?camera_id=CAM-1&limit=100` lists recent tracks.
- `GET /api/vehicle-tracks/{track_id}` includes ordered observations, frame numbers,
  event IDs and boxes.
- `GET /api/vehicle-detection-events` includes track IDs in detection boxes.
- `GET/PUT /api/camera-checkpoints/{camera_id}` reads or configures a line.
- `GET /api/checkpoint-crossings?camera_id=CAM-1` shows counted crossings.
- `GET /api/track-links/candidates` lists reviewed plate matches, and
  `POST /api/track-links` confirms a selected pair. `GET /api/track-links` shows
  confirmed links.
- These raw camera/track routes require an Administrator account.
- Migration `0006_vehicle_tracking` adds `vehicle_tracks` and `track_observations`.
  Existing events stay intact; historical frames are not assigned guessed IDs.
- Migration `0007_checkpoint_links` adds checkpoint definitions, counted crossings
  and confirmed track links. Existing observations and registry records are retained.

## Manual check

Sign in as Administrator, open **Live Camera**, and observe one vehicle in several
consecutive frames. Its displayed track suffix should remain the same while it
moves modestly. Add a second vehicle; it should receive another ID. Upload a short
recorded video and compare the result's observation count and unique track count.
In API docs, query `/api/vehicle-tracks` and open a returned ID to see its event
history. A new upload should start a new stream even with the same camera ID.
To check crossing counts, save the default centre line for the chosen camera and
use a video in which a vehicle visibly crosses it. The result should show one
crossing for that track. Refresh the panel to inspect the event. For a camera-link
check, review accepted live plate reads from two distinct cameras, refresh the
candidate list and confirm only an observation pair you can verify.

## Limits

Box overlap and centre distance are heuristic. Occlusion, crowded scenes, fast
motion, low sampling rates, class changes and camera movement can break a track or
switch identities. Crossing counts inherit those track errors and require a correctly
placed line; they count observed track crossings, not guaranteed unique physical
vehicles. Manually confirmed plate links can still be wrong if a plate is cloned or
misread. There is no automatic cross-camera reidentification or route reconstruction.
Track IDs are observational metadata, not proof of registration or identity.
Ground-truth video evaluation remains necessary before movement analytics uses
these records for alerts.

## Verification

On 10 October 2026, 136 backend tests passed against isolated PostgreSQL, including
tracking sequences with multiple same-class vehicles and separate camera/upload
streams. Six focused tests passed after the final association adjustment. The
frontend production build passed. Migration `0006_vehicle_tracking` applied to the
local Docker database with no schema drift; existing record counts stayed the same.
The live administrator track route returned 200 and an officer request returned
403. The track tables are initially empty because no new live capture was made.
