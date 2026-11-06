#!/usr/bin/env bash
# Launch agent-workspaces MCP (stdio). Secrets/paths from host .env, not mcp.json.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${KB_APP_ENV_FILE:-${HOME}/Projects/knowledge-base-bot/.env}"
PY="${AGENT_WORKSPACES_PYTHON:-${HOME}/Projects/knowledge-base-bot/.venv/bin/python}"

if [[ ! -x "${PY}" ]]; then
  PY="$(command -v python3)"
fi

# Preserve process env (cursor-agent sets AGENT_ROOT / KB_*) over empty .env values.
_PRESERVE_AGENT_ROOT="${AGENT_ROOT:-}"
_PRESERVE_SESSION="${KB_SESSION_ID:-}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -n "${_PRESERVE_AGENT_ROOT}" ]]; then
  export AGENT_ROOT="${_PRESERVE_AGENT_ROOT}"
fi
if [[ -n "${_PRESERVE_SESSION}" ]]; then
  export KB_SESSION_ID="${_PRESERVE_SESSION}"
fi

if [[ -z "${AGENT_ROOT:-}" ]]; then
  echo "agent-workspaces MCP: AGENT_ROOT is not set" >&2
  exit 1
fi

exec "${PY}" "${ROOT}/server.py"
