#!/usr/bin/env bash
# ============================================================
# deploy.sh — серверный скрипт деплоя Knowledge Base Bot
# ============================================================
# Используется:
#   - GitHub Actions (по SSH)
#   - Ручной деплой: ssh server "/opt/knowledge-base-bot/scripts/deploy.sh"
#   - Будущий админ-бот
#
# Опции:
#   --notify    Отправить результат в Telegram
#   --rollback TAG  Откатиться на указанный тег
#   --logs N    Показать последние N строк логов после деплоя
# ============================================================

set -euo pipefail

DEPLOY_DIR="/opt/knowledge-base-bot"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
CONTAINER_NAME="knowledge-base-bot"
LOG_FILE="${DEPLOY_DIR}/logs/deploy.log"
STARTUP_WAIT=15

NOTIFY=false
ROLLBACK_TAG=""
SHOW_LOGS=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --notify) NOTIFY=true; shift ;;
    --rollback) ROLLBACK_TAG="$2"; shift 2 ;;
    --logs) SHOW_LOGS="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

cd "$DEPLOY_DIR"
mkdir -p logs

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

notify_telegram() {
  local msg="$1"
  if [ "$NOTIFY" = true ]; then
    if [ -f "$DEPLOY_DIR/.env" ]; then
      local token=$(grep -E "^TELEGRAM_TOKEN=" "$DEPLOY_DIR/.env" | cut -d'=' -f2-)
      local chat_id=$(grep -E "^ADMIN_TELEGRAM_IDS=" "$DEPLOY_DIR/.env" | cut -d'=' -f2- | cut -d',' -f1)
      if [ -n "$token" ] && [ -n "$chat_id" ]; then
        curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
          -d "chat_id=${chat_id}" \
          -d "text=${msg}" > /dev/null 2>&1 || true
      fi
    fi
  fi
}

# --- Rollback ---
if [ -n "$ROLLBACK_TAG" ]; then
  log "=== Rollback to tag: $ROLLBACK_TAG ==="
  git fetch --tags
  if ! git tag -l | grep -q "^${ROLLBACK_TAG}$"; then
    log "ERROR: Tag $ROLLBACK_TAG not found"
    echo "Available tags:"
    git tag -l --sort=-v:refname | head -10
    exit 1
  fi
  git checkout "$ROLLBACK_TAG"
  $COMPOSE build bot
  $COMPOSE up -d bot
  sleep "$STARTUP_WAIT"
  STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "not_found")
  if [ "$STATUS" = "running" ]; then
    log "Rollback to $ROLLBACK_TAG successful"
    notify_telegram "🔄 Откат на $ROLLBACK_TAG выполнен. Контейнер: running"
  else
    log "ERROR: Rollback failed, container status: $STATUS"
    notify_telegram "❌ Откат на $ROLLBACK_TAG завершился с ошибкой. Статус: $STATUS"
    exit 1
  fi
  exit 0
fi

# --- Deploy ---
log "=== Deploy started ==="

log "Git pull..."
git pull origin main 2>&1 | tee -a "$LOG_FILE"

log "Building bot..."
$COMPOSE build bot 2>&1 | tail -5 | tee -a "$LOG_FILE"

log "Restarting bot..."
$COMPOSE up -d bot 2>&1 | tee -a "$LOG_FILE"

log "Waiting ${STARTUP_WAIT}s for startup..."
sleep "$STARTUP_WAIT"

# Health check
STATUS=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "not_found")
log "Container status: $STATUS"

if [ "$STATUS" = "running" ]; then
  log "=== Deploy successful ==="
  notify_telegram "✅ Деплой успешен. Контейнер: running"
else
  log "=== Deploy FAILED ==="
  $COMPOSE logs --tail=30 bot 2>&1 | tee -a "$LOG_FILE"
  notify_telegram "❌ Деплой завершился с ошибкой. Статус: $STATUS"
  exit 1
fi

if [ "$SHOW_LOGS" -gt 0 ] 2>/dev/null; then
  echo ""
  echo "=== Last $SHOW_LOGS log lines ==="
  $COMPOSE logs --tail="$SHOW_LOGS" bot 2>&1
fi
