#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${PROJECT_FM_DATA_ROOT:-$ROOT_DIR/data}"
BACKEND_PORT="${PROJECT_FM_BACKEND_PORT:-8000}"
FRONTEND_PORT="${PROJECT_FM_FRONTEND_PORT:-5173}"

mkdir -p "$DATA_ROOT"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR/backend"
PROJECT_FM_DATA_ROOT="$DATA_ROOT" .venv/bin/uvicorn project_fm.api:app --host 127.0.0.1 --port "$BACKEND_PORT" &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo "Project FM backend:  http://127.0.0.1:$BACKEND_PORT"
echo "Project FM frontend: http://127.0.0.1:$FRONTEND_PORT"
wait
