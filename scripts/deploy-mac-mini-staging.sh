#!/usr/bin/env bash
# Staging-only deploy on Mac mini. Does NOT restart prod launchd or prod compose.
# Uses a dedicated checkout (default ~/Projects/knowledge-base-bot-staging).
# Compose project: kb-staging. Ports: API 8191, miniapp 8182.
set -euo pipefail

STAGING_DIR="${KB_STAGING_DIR:-${HOME}/Projects/knowledge-base-bot-staging}"
VAULT_MAC_MINI="${HOME}/Nextcloud/Документация/Инфраструктура/mac-mini"
if [[ ! -d "${VAULT_MAC_MINI}" ]]; then
  VAULT_MAC_MINI="${HOME}/var/knowledge-base-bot/kb/Документация/Инфраструктура/mac-mini"
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:${PATH}"

cd "${STAGING_DIR}"

if [[ ! -f .env.staging ]]; then
  echo "ERROR: .env.staging missing in ${STAGING_DIR}" >&2
  echo "Copy from ${VAULT_MAC_MINI}/env.staging.example or from prod dir once." >&2
  exit 1
fi

# docker compose still reads `.env` for ${VAR} interpolation in compose YAML
# even when --env-file is set for container env.
ln -sfn .env.staging .env

if [[ -d "${VAULT_MAC_MINI}" ]]; then
  for f in docker-compose.mac-mini-staging.yml docker-compose.mac-mini-staging-ports.yml; do
    if [[ ! -f "${f}" && -f "${VAULT_MAC_MINI}/${f}" ]]; then
      cp "${VAULT_MAC_MINI}/${f}" .
      echo "Restored ${f} from vault"
    fi
  done
fi

for i in $(seq 1 30); do
  docker info >/dev/null 2>&1 && break
  sleep 2
done
docker info >/dev/null 2>&1 || { echo "Docker not ready" >&2; exit 1; }

mkdir -p logs-staging

# Explicit project name — never the prod project "knowledge-base-bot".
export DOCKER_BUILDKIT=1
docker compose -p kb-staging \
  --env-file .env.staging \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  -f docker-compose.mac-mini-staging.yml \
  -f docker-compose.mac-mini-staging-ports.yml \
  up -d --build postgres kb-app-api miniapp

echo "Staging deploy OK: $(git rev-parse --short HEAD 2>/dev/null || echo unknown) dir=${STAGING_DIR}"
echo "Health: curl -sS http://127.0.0.1:8191/health"
# Container may still be booting right after recreate.
for i in $(seq 1 30); do
  if curl -sfS http://127.0.0.1:8191/health >/dev/null; then
    curl -sfS http://127.0.0.1:8191/health
    echo
    break
  fi
  sleep 1
done
curl -sfS http://127.0.0.1:8191/health >/dev/null || echo "WARN: staging /health not ready yet"
