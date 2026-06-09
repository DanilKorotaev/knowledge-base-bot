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
fi

COMPOSE_FILES=(
  -f docker-compose.yml
  -f docker-compose.prod.yml
  -f docker-compose.mac-mini.yml
  -f docker-compose.mac-mini-ports-tailscale.yml
  -f docker-compose.mac-mini-postgres-local.yml
)
SERVICES=(postgres kb-app-api miniapp health-sync-api)

# venv бота на хосте
if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

for i in $(seq 1 30); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "Docker not ready" >&2; exit 1; }

# Обычный deploy: только перезапуск контейнеров (образы уже на mini).
# Полная пересборка: DEPLOY_BUILD=1 bash scripts/deploy-mac-mini.sh
UP_FLAGS=(-d)
if [[ "${DEPLOY_BUILD:-0}" == "1" ]]; then
  UP_FLAGS=(-d --build)
fi
docker compose "${COMPOSE_FILES[@]}" up "${UP_FLAGS[@]}" "${SERVICES[@]}"

# Перезапуск Telegram-бота на хосте (не в Docker)
UID_NUM="$(id -u)"
launchctl kickstart -k "gui/${UID_NUM}/com.coredan.kb-bot-host" 2>/dev/null \
  || launchctl bootstrap "gui/${UID_NUM}" "${HOME}/Library/LaunchAgents/com.coredan.kb-bot-host.plist" 2>/dev/null \
  || true

echo "Deploy OK: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
