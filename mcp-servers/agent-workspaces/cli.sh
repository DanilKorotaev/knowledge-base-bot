#!/usr/bin/env bash
# CLI for in-app / Cursor agents when MCP tools are unavailable.
#
# Usage:
#   bash knowledge-base-bot/mcp-servers/agent-workspaces/cli.sh ensure bot git@github.com:org/bot.git
#   bash knowledge-base-bot/mcp-servers/agent-workspaces/cli.sh list
#   bash knowledge-base-bot/mcp-servers/agent-workspaces/cli.sh release <slot_id>
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

# Prefer process AGENT_ROOT; do not invent a default that escapes the user.
if [[ -z "${AGENT_ROOT:-}" ]]; then
  echo '{"ok":false,"error":"AGENT_ROOT is not set"}' >&2
  exit 1
fi

exec "${PY}" "${ROOT}/cli.py" "$@"
