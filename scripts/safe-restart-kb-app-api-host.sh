#!/usr/bin/env bash
# Restart Mac mini host KB App API without blindly killing an in-flight cursor-agent reply.
#
# Usage:
#   bash scripts/safe-restart-kb-app-api-host.sh           # refuse if cursor-agent running
#   KB_API_RESTART_WAIT=1 bash scripts/safe-restart-kb-app-api-host.sh   # wait up to WAIT_SEC
#   KB_API_RESTART_FORCE=1 bash scripts/safe-restart-kb-app-api-host.sh  # restart anyway
#
# Exit codes: 0 ok, 2 busy (refused), 1 other failure
set -euo pipefail

LABEL="com.coredan.kb-app-api-host"
UID_NUM="$(id -u)"
FORCE="${KB_API_RESTART_FORCE:-0}"
WAIT="${KB_API_RESTART_WAIT:-0}"
WAIT_SEC="${KB_API_RESTART_WAIT_SEC:-600}"
POLL_SEC="${KB_API_RESTART_POLL_SEC:-5}"
API_PORT="${KB_APP_API_PORT:-8091}"
API_HEALTH="http://127.0.0.1:${API_PORT}/health"

cursor_agents_running() {
  # Match the CLI the host API spawns (not IDE Cursor.app).
  pgrep -f '[c]ursor-agent' >/dev/null 2>&1
}

if cursor_agents_running && [[ "${FORCE}" != "1" ]]; then
  if [[ "${WAIT}" == "1" ]]; then
    echo "cursor-agent running — waiting up to ${WAIT_SEC}s before restart of ${LABEL}..."
    elapsed=0
    while cursor_agents_running && (( elapsed < WAIT_SEC )); do
      sleep "${POLL_SEC}"
      elapsed=$((elapsed + POLL_SEC))
      echo "  still busy (${elapsed}s/${WAIT_SEC}s)"
    done
    if cursor_agents_running; then
      echo "ERROR: cursor-agent still running after ${WAIT_SEC}s." >&2
      echo "Refuse restart (would kill in-flight KB App reply). Set KB_API_RESTART_FORCE=1 to override." >&2
      exit 2
    fi
  else
    echo "ERROR: cursor-agent is running — refuse restart of ${LABEL}." >&2
    echo "Restarting now would kill the in-flight KB App / agent reply." >&2
    echo "Finish the reply first, or: KB_API_RESTART_WAIT=1 $0" >&2
    echo "Force (user-approved only): KB_API_RESTART_FORCE=1 $0" >&2
    exit 2
  fi
elif cursor_agents_running && [[ "${FORCE}" == "1" ]]; then
  echo "WARN: KB_API_RESTART_FORCE=1 — restarting ${LABEL} while cursor-agent is running" >&2
fi

if ! launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null; then
  plist="${HOME}/Library/LaunchAgents/${LABEL}.plist"
  if [[ -f "${plist}" ]]; then
    launchctl bootstrap "gui/${UID_NUM}" "${plist}" 2>/dev/null || true
    launchctl kickstart -k "gui/${UID_NUM}/${LABEL}" 2>/dev/null || true
  else
    echo "ERROR: could not kickstart ${LABEL} (plist missing: ${plist})" >&2
    exit 1
  fi
fi

for i in $(seq 1 30); do
  if curl -sf "${API_HEALTH}" >/dev/null 2>&1; then
    echo "Restart OK: ${LABEL} healthy on ${API_HEALTH}"
    exit 0
  fi
  sleep 2
done

echo "WARN: ${LABEL} restarted but health check failed: ${API_HEALTH}" >&2
tail -20 "${HOME}/Library/Logs/kb-app-api-host.log" 2>/dev/null >&2 || true
exit 1
