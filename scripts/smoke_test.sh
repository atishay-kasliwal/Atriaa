#!/usr/bin/env sh
# Smoke-test a running Atria backend: ./scripts/smoke_test.sh [base_url]
# Default base URL is the local dev server; for DigitalOcean pass https://<app>.ondigitalocean.app
set -eu
BASE="${1:-http://localhost:8000}"
fail=0

check() {
  code=$(curl -s -o /tmp/atria_smoke_body -w '%{http_code}' "$BASE$1") || code=000
  if [ "$code" = "200" ]; then echo "ok    $1"; else echo "FAIL  $1 ($code)"; fail=1; fi
}

check /health
check /queue

echo "health: $(curl -s "$BASE/health")"
exit $fail
