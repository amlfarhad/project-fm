#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PROJECT_FM_STATIC_PORT:-4187}"

cd "$ROOT_DIR"
python3 -m http.server "$PORT" --directory "$ROOT_DIR/frontend/dist" >/tmp/project-fm-static-server.log 2>&1 &
SERVER_PID=$!
cleanup() {
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in {1..50}; do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "Static server exited before binding port $PORT."
    cat /tmp/project-fm-static-server.log
    exit 1
  fi
  if curl -fsS "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

PROJECT_FM_FRONTEND_URL="http://127.0.0.1:$PORT" PROJECT_FM_EXPECT_HOSTED=1 node "$ROOT_DIR/scripts/browser-smoke.mjs"
