#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="$(mktemp -d)"
BACKEND_PORT="${PROJECT_FM_BACKEND_PORT:-8000}"
FRONTEND_PORT="${PROJECT_FM_FRONTEND_PORT:-5173}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  rm -rf "$DATA_ROOT"
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR/backend"
PROJECT_FM_DATA_ROOT="$DATA_ROOT" .venv/bin/uvicorn project_fm.api:app --host 127.0.0.1 --port "$BACKEND_PORT" --log-level warning &
BACKEND_PID=$!

cd "$ROOT_DIR/frontend"
npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort &
FRONTEND_PID=$!

for _ in {1..80}; do
  if curl -fsS "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1 &&
    curl -fsS "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

PROJECT_FM_FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT" node "$ROOT_DIR/scripts/browser-smoke.mjs"
