#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: ./scripts/trial-file.sh /absolute/path/to/match.mp4 [duration_ms] [sample_every_ms]"
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VIDEO_PATH="$1"
DURATION_MS="${2:-}"
SAMPLE_EVERY_MS="${3:-1000}"

cd "$ROOT_DIR/backend"
ARGS=(
  --match-id trial
  --source-type file
  --path "$VIDEO_PATH"
  --sample-every-ms "$SAMPLE_EVERY_MS"
)

if [[ -n "$DURATION_MS" ]]; then
  ARGS+=(--duration-ms "$DURATION_MS")
fi

.venv/bin/python -m project_fm.trial "${ARGS[@]}"
