#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/backend"
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,video]"

cd "$ROOT_DIR/frontend"
npm install

echo "Project FM local setup complete."
