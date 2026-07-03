#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
.venv/bin/pytest -v

cd "$ROOT_DIR/frontend"
npm run build
npm audit --audit-level=moderate

cd "$ROOT_DIR"
./scripts/browser-smoke.sh

secret_findings="$(rg -n "sk-|api_key|secret|password|/Users/|\\.env" . \
  --glob '!frontend/package-lock.json' \
  --glob '!docs/**' \
  --glob '!backend/.venv/**' \
  --glob '!frontend/node_modules/**' \
  --glob '!frontend/dist/**' \
  --glob '!data/**' \
  --glob '!scripts/verify-local.sh' \
  --glob '!.playwright-mcp/**' || true)"
secret_findings="$(printf "%s\n" "$secret_findings" | rg -v "PROJECT_FM_DATA_ROOT|PROJECT_FM_DETECTOR|PROJECT_FM_YOLO_MODEL|PROJECT_FM_API_TOKEN|VITE_PROJECT_FM_API_TOKEN|process\\.env" || true)"
if [[ -n "$secret_findings" ]]; then
  printf "%s\n" "$secret_findings"
  echo "Secret/privacy scan failed."
  exit 1
fi

email_findings="$(rg -n "[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}" . -i \
  --glob '!frontend/package-lock.json' \
  --glob '!docs/**' \
  --glob '!backend/.venv/**' \
  --glob '!frontend/node_modules/**' \
  --glob '!frontend/dist/**' \
  --glob '!data/**' \
  --glob '!.playwright-mcp/**' || true)"
if [[ -n "$email_findings" ]]; then
  printf "%s\n" "$email_findings"
  echo "Email/privacy scan failed."
  exit 1
fi

echo "Project FM verification complete."
