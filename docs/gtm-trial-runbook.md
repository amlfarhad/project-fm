# Project FM Trial Runbook

## Trial Objective

Prove that Project FM can turn club-supplied match video into a usable 2D tactical map with measurable latency, observed-player coverage, identity coverage, and exportable state data.

## Local Trial Setup

```bash
make setup
make verify
```

Optional protected local-network run:

```bash
PROJECT_FM_API_TOKEN=<shared-token> make dev
```

## Analyst Workflow

1. Start Project FM with `make dev`.
2. Open `http://127.0.0.1:5173`.
3. Use Analyst view for file, stream URL, or browser capture ingestion.
4. Confirm the System panel shows:
   - `Processor` as `opencv`, `opencv-live`, or `yolo-person-green-pitch`.
   - `Observed` player count.
   - `Observed IDs` for shirt-number coverage from observed detections.
   - Processing FPS and speed.
   - No critical quality warnings.
5. Use Track Corrections to lock team, shirt number, player name, and role.
6. Export CSV or JSONL for analyst review.

## Command-Line Trial Gate

```bash
make trial VIDEO=/absolute/path/to/match.mp4 DURATION_MS=60000 SAMPLE_EVERY_MS=1000
```

The command prints a JSON report and exits non-zero when hard thresholds fail. Read `trial_status` before treating a run as club-ready:

- `pass`: thresholds passed and no quality warnings were emitted.
- `pass_with_warnings`: thresholds passed, but analyst review or model tuning is still required before pitching the clip as a clean tactical reconstruction.
- `fail`: one or more hard thresholds failed.

Recommended first-pass thresholds:

- `min_states >= 2`
- `min_observed_players >= 6` for broadcast footage, higher for tactical/high-angle feeds
- `min_calibration_confidence >= 0.6`
- `min_processing_fps >= 1.0` on MacBook Air, higher on a GPU workstation
- `min_observed_identity_coverage >= 0.0` before OCR/model tuning, then increase after kit calibration

GTM trials require decoded video frames. The explicit development-only `allow_baseline_fallback` path is not accepted as GTM-ready and fails the trial gate.

## Pass Criteria For A Real Club Pilot

Project FM should not be pitched as fully adopted until it passes on at least three club-supplied clips:

- Wide tactical/high broadcast angle.
- Normal TV broadcast angle.
- Live browser or stream URL ingest.

Minimum pilot pass:

- App starts from `make dev`.
- `make verify` passes.
- Trial gate returns `trial_status: pass` on at least one supplied clip.
- Analyst can correct identities and export CSV/JSONL.
- Manager view updates after ingest without console errors.
- API token protection works when enabled.

## Current Known Risk Areas

- Broadcast cuts and closeups can interrupt re-identification.
- Shirt-number OCR works on clear jersey crops, but low-resolution broadcast views require stronger OCR/model support.
- Full 22-player reconstruction still depends on estimated rest-defense positions when players are off-camera.
- Browser capture requires a human to approve the OS picker.
