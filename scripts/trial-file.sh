#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/trial-file.sh /absolute/path/to/match.mp4 [duration_ms] [sample_every_ms] [min_states] [min_observed_players] [min_calibration_confidence] [min_processing_fps] [min_identity_coverage] [min_observed_identity_coverage]"
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIDEO_PATH="$1"
DURATION_MS="${2:-}"
SAMPLE_EVERY_MS="${3:-1000}"
MIN_STATES="${4:-2}"
MIN_OBSERVED_PLAYERS="${5:-6}"
MIN_CALIBRATION_CONFIDENCE="${6:-0.6}"
MIN_PROCESSING_FPS="${7:-1.0}"
MIN_IDENTITY_COVERAGE="${8:-0.0}"
MIN_OBSERVED_IDENTITY_COVERAGE="${9:-0.0}"

cd "$ROOT_DIR/backend"
ARGS=(
  --match-id trial
  --source-type file
  --path "$VIDEO_PATH"
  --sample-every-ms "$SAMPLE_EVERY_MS"
  --min-states "$MIN_STATES"
  --min-observed-players "$MIN_OBSERVED_PLAYERS"
  --min-calibration-confidence "$MIN_CALIBRATION_CONFIDENCE"
  --min-processing-fps "$MIN_PROCESSING_FPS"
  --min-identity-coverage "$MIN_IDENTITY_COVERAGE"
  --min-observed-identity-coverage "$MIN_OBSERVED_IDENTITY_COVERAGE"
)

if [[ -n "$DURATION_MS" ]]; then
  ARGS+=(--duration-ms "$DURATION_MS")
fi

.venv/bin/python -m project_fm.trial "${ARGS[@]}"
