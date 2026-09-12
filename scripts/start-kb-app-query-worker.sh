#!/usr/bin/env bash
# Background Cursor query worker (separate from uvicorn). Survives API redeploy.
set -euo pipefail

eval "$(/opt/homebrew/bin/brew shellenv)"
export PATH="${HOME}/.local/bin:/opt/homebrew/opt/ruby@3.3/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

API_DIR="${HOME}/Projects/knowledge-base-bot"
cd "${API_DIR}"

if [[ ! -d .venv ]]; then
  echo "venv missing — run setup first" >&2
  exit 1
fi

if ! lsof -nP -iTCP:1080 -sTCP:LISTEN 2>/dev/null | grep -q ss-local; then
  "${HOME}/VPN/start-kb-vpn.sh" --once || true
fi
if ! lsof -nP -iTCP:8118 -sTCP:LISTEN >/dev/null 2>&1; then
  "${HOME}/VPN/vpn-http.sh" on || true
fi

# Load .env without clobbering already-exported overrides
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-5432}"
export TELEGRAM_PROXY="${TELEGRAM_PROXY:-socks5://127.0.0.1:1080}"
export OPENAI_PROXY="${OPENAI_PROXY:-socks5://127.0.0.1:1080}"
if [[ -n "${CURSOR_CLI_PROXY:-}" ]]; then
  case "${CURSOR_CLI_PROXY}" in
    socks5://*|socks://*|socks5h://*)
      echo "WARN: CURSOR_CLI_PROXY is SOCKS; forcing http://127.0.0.1:8118" >&2
      export CURSOR_CLI_PROXY="http://127.0.0.1:8118"
      ;;
  esac
else
  export CURSOR_CLI_PROXY="http://127.0.0.1:8118"
fi
export NODE_USE_ENV_PROXY="${NODE_USE_ENV_PROXY:-1}"
export AGENT_CLI_CREDENTIAL_STORE="${AGENT_CLI_CREDENTIAL_STORE:-file}"
export CURSOR_CLI_USE_STDBUF="${CURSOR_CLI_USE_STDBUF:-false}"
export PYTHONPATH="${API_DIR}/packages/health_linking:${PYTHONPATH:-}"
export MAX_CONCURRENT_QUERY_JOBS="${MAX_CONCURRENT_QUERY_JOBS:-2}"

exec "${API_DIR}/.venv/bin/python" -m kb_app_api.query_jobs.worker
