#!/usr/bin/env bash
# Live auth smoke against staging (or BASE_URL). No secrets / real FQDNs in git.
# Usage:
#   BASE_URL=https://kbapp-staging.example.com ./scripts/staging_auth_smoke.sh
#   BASE_URL=http://127.0.0.1:8191 ./scripts/staging_auth_smoke.sh
set -euo pipefail

BASE_URL="${BASE_URL:?set BASE_URL to your staging API origin}"
BASE_URL="${BASE_URL%/}"
SUFFIX="$(date +%s | tail -c 6)"
USER_A="smoke_a_${SUFFIX}"
USER_B="smoke_b_${SUFFIX}"
PASS='StagingSmokePass123!'

json_field() {
  python3 -c 'import sys,json; d=json.load(sys.stdin); print(d'"$1"')'
}

echo "== health =="
curl -sfS -m 15 "${BASE_URL}/health" | grep -q '"status"' 
echo "ok"

echo "== signup-status =="
curl -sfS -m 15 "${BASE_URL}/api/auth/signup-status"
echo

echo "== register ${USER_A} =="
REG_A="$(curl -sfS -m 45 -X POST "${BASE_URL}/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"login\":\"${USER_A}\",\"password\":\"${PASS}\",\"email\":\"${USER_A}@example.com\"}")"
TOKEN_A="$(echo "${REG_A}" | json_field '["access_token"]')"
VAULT_A="$(echo "${REG_A}" | json_field '["user"]["vault_root_relative"]')"
echo "vault=${VAULT_A}"

echo "== register ${USER_B} =="
REG_B="$(curl -sfS -m 45 -X POST "${BASE_URL}/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"login\":\"${USER_B}\",\"password\":\"${PASS}\",\"email\":\"${USER_B}@example.com\"}")"
TOKEN_B="$(echo "${REG_B}" | json_field '["access_token"]')"

echo "== me =="
curl -sfS -m 15 "${BASE_URL}/api/auth/me" -H "Authorization: Bearer ${TOKEN_A}" | grep -q "${USER_A}"
echo "ok"

echo "== refresh =="
REFRESH="$(echo "${REG_A}" | json_field '["refresh_token"]')"
REF="$(curl -sfS -m 15 -X POST "${BASE_URL}/api/auth/refresh" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"${REFRESH}\"}")"
TOKEN_A2="$(echo "${REF}" | json_field '["access_token"]')"
test -n "${TOKEN_A2}"
echo "ok"

echo "== sessions isolation =="
SID_A="$(curl -sfS -m 30 -X POST "${BASE_URL}/api/sessions" \
  -H "Authorization: Bearer ${TOKEN_A2}" \
  -H 'Content-Type: application/json' \
  -d '{"title":"A only","use_knowledge_base":false}' | json_field '["session"]["id"]')"
CODE="$(curl -sS -m 15 -o /tmp/b_forbidden.json -w '%{http_code}' \
  "${BASE_URL}/api/sessions/${SID_A}/messages" \
  -H "Authorization: Bearer ${TOKEN_B}")"
test "${CODE}" = "403" -o "${CODE}" = "404"
echo "B cannot read A session (HTTP ${CODE})"

echo "== devices =="
DEV="smoke-device-${SUFFIX}"
curl -sfS -m 15 -X POST "${BASE_URL}/api/devices" \
  -H "Authorization: Bearer ${TOKEN_A2}" \
  -H 'Content-Type: application/json' \
  -d "{\"device_token\":\"${DEV}\",\"platform\":\"ios\",\"apns_environment\":\"sandbox\"}" >/dev/null
echo "registered"

echo "STAGING AUTH SMOKE OK (${BASE_URL})"
