#!/usr/bin/env bash
# Launch agent-workspaces MCP (stdio). Secrets/paths from host .env, not mcp.json.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${KB_APP_ENV_FILE:-${HOME}/Projects/knowledge-base-bot/.env}"
PY="${AGENT_WORKSPACES_PYTHON:-${HOME}/Projects/knowledge-base-bot/.venv/bin/python}"

if [[ ! -x "${PY}" ]]; then
  PY="$(command -v python3)"
fi

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

exec "${PY}" "${ROOT}/server.py"
