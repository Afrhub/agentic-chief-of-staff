#!/usr/bin/env bash
# End-to-end smoke test for the self-hosted stack.
# Assumes `make up` has been run. Validates: health -> DB write (seed) ->
# routing through nginx -> coordinator suppression rule -> (if LLM keys present)
# the full surface->decide loop.
set -euo pipefail

cd "$(dirname "$0")"
COMPOSE="docker compose -f docker-compose.prod.yml"
WEB_PORT="${WEB_PORT:-8080}"
BASE="http://localhost:${WEB_PORT}"
FID="demo-founder"

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }

echo "==> 1. Waiting for /health (through nginx)…"
for i in $(seq 1 40); do
  if curl -fsS "$BASE/health" 2>/dev/null | grep -q '"status":"ok"'; then
    pass "health is ok"; break
  fi
  [ "$i" = 40 ] && fail "health never came up"; sleep 2
done

echo "==> 2. Seeding demo founder (proves DB write)…"
$COMPOSE exec -T backend python seed.py | sed 's/^/     /'
pass "seed ran"

echo "==> 3. GET alerts (proves DB read + routing)…"
ALERTS=$(curl -fsS "$BASE/founders/$FID/alerts?status=active")
echo "$ALERTS" | grep -q '^\[' || fail "alerts endpoint did not return a JSON array: $ALERTS"
pass "alerts endpoint returns an array"

echo "==> 4. POST a single signal -> must be SUPPRESSED (>=2-signal rule, no LLM needed)…"
SUP=$(curl -fsS -X POST "$BASE/founders/$FID/alerts" \
  -H 'Content-Type: application/json' \
  -d '{"signals":[{"type":"revenue_anomaly","confidence":0.9,"data":{}}]}')
echo "$SUP" | grep -q '"status":"suppressed"' || fail "single signal was not suppressed: $SUP"
pass "single signal correctly suppressed"

# --- Full loop requires a working LLM (real keys, or LLM_MODE=local with a model pulled) ---
if grep -qE '^(ANTHROPIC_API_KEY|OPENAI_API_KEY)=.+' .env 2>/dev/null || grep -q '^LLM_MODE=local' .env 2>/dev/null; then
  echo "==> 5. POST two distinct signals -> should SURFACE (LLM configured)…"
  OUT=$(curl -fsS -X POST "$BASE/founders/$FID/alerts" \
    -H 'Content-Type: application/json' \
    -d '{"signals":[{"type":"revenue_anomaly","confidence":0.9,"data":{"mrr":16000}},{"type":"churn_signal","confidence":0.85,"data":{}}]}')
  echo "$OUT" | grep -q '"status":"surfaced"' || fail "two signals did not surface (LLM reachable?): $OUT"
  AID=$(echo "$OUT" | grep -o '"alert_id":"[^"]*"' | head -1 | sed 's/.*:"//;s/"//')
  pass "alert surfaced (id=$AID)"

  echo "==> 6. POST a decision, then read it back…"
  curl -fsS -X POST "$BASE/founders/$FID/alerts/$AID/decide" \
    -H 'Content-Type: application/json' -d '{"decision_text":"smoke-test decision"}' \
    | grep -q '"status":"recorded"' || fail "decision not recorded"
  curl -fsS "$BASE/founders/$FID/decisions?limit=5" | grep -q 'smoke-test decision' \
    || fail "decision not found in history"
  pass "decision recorded and retrievable"
else
  echo "==> 5-6. Skipped surface/decide loop (no LLM keys in .env; set them to test the full path)."
fi

echo
echo "✅ Smoke test passed."
