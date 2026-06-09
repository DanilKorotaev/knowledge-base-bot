#!/usr/bin/env bash
# Деплой runtime на Mac mini после git pull (GitHub Actions self-hosted).
# Не удаляет .env, Docker volumes, ~/var/knowledge-base-bot/kb.
set -euo pipefail

RUNTIME_DIR="${KB_RUNTIME_DIR:-${HOME}/Projects/knowledge-base-bot}"
VAULT_MAC_MINI="${HOME}/Nextcloud/Документация/Инфраструктура/mac-mini"

export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:${PATH}"

cd "${RUNTIME_DIR}"

if [[ ! -f .env ]]; then
  echo "ERROR: .env missing in ${RUNTIME_DIR}" >&2
  exit 1
fi

# Локальные оверрайды (не в public git) — из vault, если пропали
if [[ -d "${VAULT_MAC_MINI}" ]]; then
  for f in docker-compose.mac-mini.yml \
           docker-compose.mac-mini-ports-tailscale.yml \
           docker-compose.mac-mini-postgres-local.yml; do
    if [[ ! -f "${f}" && -f "${VAULT_MAC_MINI}/${f}" ]]; then
      cp "${VAULT_MAC_MINI}/${f}" .
      echo "Restored ${f} from vault"
    fi
  done
  if [[ -f "${VAULT_MAC_MINI}/com.coredan.kb-app-api-host.plist" ]]; then
    cp "${VAULT_MAC_MINI}/com.coredan.kb-app-api-host.plist" \
      "${HOME}/Library/LaunchAgents/com.coredan.kb-app-api-host.plist"
  fi
fi

chmod +x scripts/start-kb-app-api-host.sh 2>/dev/null || true

COMPOSE_FILES=(
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.mac-mini.yml
  -f docker-compose.mac-mini-ports-tailscale.yml
  -f docker-compose.mac-mini-postgres-local.yml
)
# kb-app-api — на хосте; bot — на хосте
SERVICES=(postgres miniapp health-sync-api)

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

for i in $(seq 1 30); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "Docker not ready" >&2; exit 1; }

# Освободить :8091 для uvicorn на хосте
docker compose "${COMPOSE_FILES[@]}" stop kb-app-api 2>/dev/null || true

UP_FLAGS=(-d)
if [[ "${DEPLOY_BUILD:-0}" == "1" ]]; then
  UP_FLAGS=(-d --build)
fi
docker compose "${COMPOSE_FILES[@]}" up "${UP_FLAGS[@]}" "${SERVICES[@]}"

UID_NUM="$(id -u)"
for label in com.coredan.kb-bot-host com.coredan.kb-app-api-host; do
  launchctl kickstart -k "gui/${UID_NUM}/${label}" 2>/dev/null \
    || launchctl bootstrap "gui/${UID_NUM}" "${HOME}/Library/LaunchAgents/${label}.plist" 2>/dev/null \
    || true
done

# API на хосте: после kickstart uvicorn + DB init могут занять >2 с
API_PORT="$(grep -E '^KB_APP_API_PORT=' .env 2>/dev/null | cut -d= -f2 || true)"
API_PORT="${API_PORT:-8091}"
API_HEALTH="http://127.0.0.1:${API_PORT}/health"
for i in $(seq 1 30); do
  if curl -sf "${API_HEALTH}" >/dev/null; then
    break
  fi
  if [[ "${i}" -eq 30 ]]; then
    echo "WARN: kb-app-api health check failed after 60s (${API_HEALTH})" >&2
    tail -20 "${HOME}/Library/Logs/kb-app-api-host.log" 2>/dev/null >&2 || true
    exit 1
  fi
  sleep 2
done

echo "Deploy OK: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
