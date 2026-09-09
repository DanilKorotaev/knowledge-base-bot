#!/usr/bin/env bash
# KB App API на хосте macOS (uvicorn + cursor-agent, как бот на venv).
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

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-5432}"
export TELEGRAM_PROXY="${TELEGRAM_PROXY:-socks5://127.0.0.1:1080}"
export OPENAI_PROXY="${OPENAI_PROXY:-socks5://127.0.0.1:1080}"
# CRITICAL: cursor-agent (Node) cannot use SOCKS. Always HTTP CONNECT :8118.
# Do not default to $OPENAI_PROXY (socks) — that strips HTTPS_PROXY and breaks auth
# ("The provided API key is invalid" from RU / no egress).
if [[ -n "${CURSOR_CLI_PROXY:-}" ]]; then
  case "${CURSOR_CLI_PROXY}" in
    socks5://*|socks://*|socks5h://*)
      echo "WARN: CURSOR_CLI_PROXY is SOCKS (${CURSOR_CLI_PROXY}); forcing http://127.0.0.1:8118" >&2
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

# launchd (Aqua) может читать ~/Documents; SSH — нет. Копируем .p8 в secrets при старте.
bootstrap_apns_auth_key() {
  local secrets_dir="${API_DIR}/secrets"
  local secrets_key="${secrets_dir}/AuthKey_8H282799Z5.p8"
  local docs_key="${HOME}/Documents/AuthKey_8H282799Z5.p8"
  if [[ -f "${secrets_key}" ]]; then
    return 0
  fi
  if [[ ! -f "${docs_key}" ]]; then
    return 0
  fi
  mkdir -p "${secrets_dir}"
  if cp "${docs_key}" "${secrets_key}"; then
    chmod 600 "${secrets_key}"
    echo "APNs auth key copied to ${secrets_key}" >&2
  else
    echo "WARN: could not copy APNs key from ${docs_key}" >&2
  fi
}
bootstrap_apns_auth_key

PORT="${KB_APP_API_PORT:-8091}"
# Default 1: uvicorn --workers>1 on macOS LaunchAgent leaves :8091 in CLOSED and refuses connections.
WORKERS="${KB_APP_API_WORKERS:-1}"

UVICORN_ARGS=(kb_app_api.main:app --host 0.0.0.0 --port "${PORT}")
if [[ "${WORKERS}" -gt 1 ]]; then
  UVICORN_ARGS+=(--workers "${WORKERS}")
fi

exec "${API_DIR}/.venv/bin/uvicorn" "${UVICORN_ARGS[@]}"
