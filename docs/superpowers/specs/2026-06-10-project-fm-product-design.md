# Project FM Product Design

Date: 2026-06-10

## Core Bet

Project FM is a live tactical reconstruction system for football clubs. It ingests match video, reconstructs the full match state on a 2D pitch, and gives managers and analysts a clean real-time view of team shape, player positions, and tactical structure.

The product does not try to make broadcast footage look prettier. It converts imperfect video into a coach-readable tactical model.

## Target Users

- Touchline manager: needs a simple, low-latency 2D view that makes shape and spacing obvious.
- Match analyst: monitors tracking confidence, corrects errors, and uses richer overlays.
- Technical staff: reviews exported state data and tactical moments after the match.

## Product Principle

Visible players are observed. Off-screen players are estimated. The system tracks confidence internally and avoids pretending low-confidence estimates are certain.

The manager view stays clean. The analyst view exposes uncertainty, corrections, diagnostics, and source video overlays.

## Strongest Competing Approaches

### Approach A: Broadcast-first live reconstruction

Build the product around broadcast or club video feeds from the beginning. Treat full-match files as stream-like sources for development, then add live ingest sources without changing downstream pipeline interfaces.

Benefits:
- Matches the real product vision.
- Avoids building a dead-end notebook or demo.
- Makes every module accountable to live latency and full-match scale.

Risks:
- Harder early development.
- Accuracy may be uneven until calibration, tracking, and identity modules mature.
- MacBook Air development will run slower than real time.

Decision: choose this approach.

### Approach B: Tactical-camera-only tracking

Start with a wide elevated tactical feed and solve detection, tracking, and 2D mapping under easier visual conditions.

Benefits:
- Faster path to clean tracking.
- Closer to some existing club analysis workflows.

Risks:
- Does not satisfy the product promise that any accessible match feed can be processed.
- Weakens the pitch to clubs that do not have tactical camera access.

Decision: reject as the core architecture, but support tactical feeds as an input type.

### Approach C: UI-first analyst product with precomputed data

Build the 2D manager/analyst interface first and use precomputed or manually curated tracking data while the AI backend catches up.

Benefits:
- Fastest way to create something visually persuasive.
- Useful for product storytelling.

Risks:
- Too easy to become a facade.
- Does not prove the hardest product claim.

Decision: reject as the main path. The UI must be connected to real pipeline output from the start, even if early accuracy is limited.

## System Architecture

Project FM is built as a source-agnostic streaming pipeline:

```text
video source
  -> ingest stream
  -> frame normalization
  -> player and ball detection
  -> multi-object tracking
  -> team and role classification
  -> pitch calibration
  -> pixel-to-pitch mapping
  -> world-state estimation
  -> tactical state stream
  -> manager and analyst web clients
```

Every source is treated as a stream. A full-match file is read sequentially with timestamps, so the rest of the system behaves as if the match is live.

## Runtime Modes

### Development Mode

Runs on Amal's MacBook Air. It must accept full-match files and process them sequentially. It may run slower than real time, but it must preserve live-style interfaces, timestamps, and state emission.

Supported first:
- `.mp4`, `.mov`, and `.mkv` match files.
- Reduced frame-rate processing for laptop feasibility.
- Cached intermediate outputs for detector and tracker results.
- Browser-based manager and analyst clients on localhost.

### Matchday Product Mode

Runs with a local stadium GPU box near the analyst bench. The GPU box receives video, runs inference, and streams tactical state to iPads and MacBooks over local network.

Target supported sources:
- Full-match file.
- HDMI/SDI capture card.
- RTSP, SRT, or HLS stream when available.
- Screen or window capture when frames are legally and technically accessible.
- Local network video stream.

Non-negotiable rule: downstream modules receive the same `Frame` interface regardless of source.

## Frame Interface

Each frame emitted by ingest includes:

```text
Frame {
  frame_id: string
  source_id: string
  source_type: file | capture_card | stream_url | screen_capture | camera
  timestamp_ms: number
  wall_clock_ms: number
  image: image buffer
  width: number
  height: number
  fps_hint: number | null
  ingest_latency_ms: number | null
}
```

## Tactical State Interface

The pipeline emits tactical states:

```text
TacticalState {
  match_id: string
  timestamp_ms: number
  frame_id: string
  phase: in_possession | out_of_possession | transition | set_piece | unknown
  ball: BallState | null
  players: PlayerState[]
  pitch_calibration: CalibrationState
  system_confidence: number
}
```

Each player state includes:

```text
PlayerState {
  track_id: string
  team: home | away | referee | unknown
  shirt_number: number | null
  role_hint: goalkeeper | defender | midfielder | forward | referee | unknown
  pitch_x: number
  pitch_y: number
  observed: boolean
  confidence: number
  last_observed_ms: number
  source_bbox: [x, y, width, height] | null
}
```

## Detection And Tracking

The first implementation should use available computer vision models rather than training custom models immediately. The detection layer should support model swapping.

Initial targets:
- Detect players and referees.
- Detect the ball when feasible, but do not block the product on perfect ball detection.
- Track players over time using a multi-object tracker.
- Preserve stable `track_id` values across normal movement and short occlusions.

Known hard cases:
- Broadcast cuts.
- Closeups.
- Replays.
- Players occluding each other.
- Heavy compression.
- Scoreboards and overlays.

The system must tag or suppress non-live segments where possible, especially replays and closeups that do not represent the current game state.

## Team And Identity

Team classification starts with kit color clustering and improves over time with roster metadata, shirt-number recognition, and analyst corrections.

Initial requirements:
- Classify visible players into home, away, referee, or unknown.
- Keep classification confidence per track.
- Allow analyst correction of team assignment.
- Persist corrections across later frames.

Shirt-number recognition is a required product module, but not the first blocker. It should be added after the tracking and 2D mapping loop is functional.

## Pitch Calibration And Mapping

The system maps image pixels to pitch coordinates using visible pitch lines and camera geometry. Calibration must be temporal, not frame-isolated: it should smooth camera movement and use previous calibration when current frames are ambiguous.

Initial requirements:
- Detect field lines or accept analyst-assisted calibration.
- Estimate homography when enough pitch geometry is visible.
- Map detected player foot points to normalized pitch coordinates.
- Emit calibration confidence.
- Fall back gracefully when calibration is weak.

## Off-Screen Player Estimation

The product must render a full-pitch tactical state even when broadcast footage does not show every player.

Estimation inputs:
- Last observed position and velocity.
- Ball location or ball-side inference.
- Possession phase.
- Team shape.
- Player role.
- Formation prior.
- Player historical tendencies when available.

Practical assumption:
During settled possession, missing attacking-team defenders and goalkeeper often remain in rest-defense positions. The system can estimate them with relatively high confidence until play state changes.

Risk handling:
- If a player has not been observed recently, confidence decays.
- During fast transitions, set pieces, camera cuts, or long unseen intervals, confidence drops faster.
- Analyst view exposes low-confidence players.
- Manager view remains visually clean but can optionally mark low-confidence system states.

## Manager View

The manager view is a touchline-readable web client for iPad or MacBook.

Requirements:
- Full-pitch 2D view.
- Team-colored circles.
- Ball marker when available.
- Current team shape.
- Minimal controls.
- Low visual noise.
- Fast loading.
- Works on tablet and laptop browser.
- No fake controls or dead UI.

The manager view should favor clarity over exhaustive diagnostics.

## Analyst View

The analyst view is an operator console for MacBook.

Requirements:
- Source video with detection/tracking overlay.
- 2D pitch reconstruction.
- Confidence diagnostics.
- Team assignment corrections.
- Track merge/split correction hooks.
- Calibration status.
- Match timeline.
- Export controls for tactical state data.

Manual correction is not a weakness. It is a trust feature for a club-grade product.

## Data And Persistence

Development mode stores:
- Match metadata.
- Frame processing progress.
- Detection outputs.
- Track outputs.
- Calibration outputs.
- Tactical state timeline.
- Analyst corrections.

Use durable local files or a lightweight local database first. Avoid hardcoding one sample match path into the product.

## Latency Targets

Development mode:
- Correctness and full-match processing matter more than real-time speed.
- The app must report processing FPS and estimated live latency.

Matchday mode:
- Target 1-3 seconds end-to-end latency from accessible feed to tactical view.
- Under 1 second is desirable but not required for the first production architecture.

## Legal And Access Constraints

The system can process video frames it can legally and technically access. Some browser streams may block capture through DRM, platform restrictions, or terms of service.

The product promise is not "bypass any video source." The honest product promise is:

If Project FM can access the frames from a match feed, it can run them through the live tactical reconstruction pipeline.

## Security And Privacy

The product must not ship with:
- Hardcoded private paths.
- Private emails.
- API keys.
- Match feed credentials.
- Unlicensed copyrighted video samples in the repo.

Outreach contact lists must use publicly available professional contact data only. Do not invent emails or scrape private contact information.

## First Shippable Version

The first shippable version is not a toy demo. It is a real product slice that processes full-match files through the same interfaces intended for live operation.

In scope:
- Full-match file ingest.
- Sequential frame processing.
- Player detection.
- Basic multi-object tracking.
- Basic team color classification.
- Initial pitch mapping, with assisted calibration allowed.
- Tactical state timeline output.
- Manager 2D pitch web client.
- Analyst web client with video, overlay, diagnostics, and state playback.
- Local persistence for outputs and corrections.
- Processing status, errors, and logs.

Out of scope for first shippable version:
- Guaranteed real-time speed on MacBook Air.
- Perfect shirt-number identification.
- Fully automatic handling of every broadcast cut/replay.
- Cloud deployment.
- Native iPad app.
- Club-wide multi-user account system.
- Private MLS contact scraping.

## Acceptance Checks

The first shippable version passes when:

1. A user can select or configure a full-match video file.
2. The pipeline reads the file sequentially and records frame progress.
3. The detector produces player detections for sampled frames.
4. The tracker emits stable track IDs across ordinary movement.
5. The team classifier assigns visible tracks to home, away, referee, or unknown.
6. The calibration module maps at least some observed players onto normalized pitch coordinates.
7. The world-state module emits `TacticalState` records over time.
8. The manager view renders a full-pitch 2D tactical map from real pipeline output.
9. The analyst view shows source video, tracking overlay, confidence, and corrections.
10. The system can resume from cached intermediate outputs.
11. The UI has no dead primary controls.
12. The app reports processing FPS and latency estimates.
13. The repo contains no private credentials, copyrighted video files, or private outreach data.

## Verification Plan

Minimum verification before calling the first version complete:

- Run unit tests for ingest, state schema, and transformation utilities.
- Run backend smoke test on a short segment extracted from a full-match file.
- Run UI build and lint checks.
- Run browser QA on manager and analyst views at laptop and tablet-sized viewports.
- Run a privacy/security scan for secrets and private local paths.

If a check cannot run, report `UNVERIFIABLE` with the reason.

## Kill Criteria And Risks

The architecture should change if:

- Full-match file processing cannot be made resumable.
- Pitch calibration cannot reach useful stability from broadcast footage plus assisted fallback.
- The UI cannot clearly distinguish system confidence for analysts.
- Local development becomes impossible without GPU access.
- Legal video access constraints make live feed ingestion impractical for the intended pitch.

The product should not be pitched to clubs as matchday-ready until it has been tested on multiple full matches with different camera styles and has a measured latency/accuracy report.
