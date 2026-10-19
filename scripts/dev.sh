#!/usr/bin/env sh
# Start the whole product: Atria API on :8001 and the ER Priority app on :3000.
# Open http://localhost:3000 (patients: /checkin, nurses: /nurse). Ctrl-C stops both.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
.venv/bin/python -m uvicorn --app-dir backend main:app --host 127.0.0.1 --port 8001 &
API=$!
trap 'kill $API 2>/dev/null' EXIT INT TERM
cd er-priority/frontend
[ -d node_modules ] || npm ci
ATRIA_API_URL=http://127.0.0.1:8001 npx next dev -p 3000
