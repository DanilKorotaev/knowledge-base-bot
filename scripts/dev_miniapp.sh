#!/bin/bash

# ============================================================
# Скрипт для локальной разработки с Mini App + Cloudflare Tunnel
# ============================================================
#
# Что делает:
# 1. Запускает cloudflared tunnel → получает HTTPS URL
# 2. Автоматически прописывает MINIAPP_URL в .env
# 3. Запускает docker-compose up (postgres + miniapp + bot)
# 4. При Ctrl+C — останавливает всё и очищает MINIAPP_URL
#
# Требования:
#   brew install cloudflared
#   docker + docker-compose
#
# Использование:
#   ./scripts/dev_miniapp.sh              # полный запуск
#   ./scripts/dev_miniapp.sh --tunnel-only # только туннель (docker уже запущен)
#   ./scripts/dev_miniapp.sh --no-build    # без пересборки образов
# ============================================================

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Конфигурация
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TUNNEL_LOG="/tmp/cloudflared_miniapp_$$.log"
ENV_FILE="$PROJECT_DIR/.env"

# Флаги
TUNNEL_ONLY=false
NO_BUILD=false
for arg in "$@"; do
    case "$arg" in
        --tunnel-only) TUNNEL_ONLY=true ;;
        --no-build)    NO_BUILD=true ;;
    esac
done

# PID-ы
TUNNEL_PID=""
DOCKER_STARTED=false

# ============================================================
# Cleanup при выходе
# ============================================================
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Останавливаю всё...${NC}"

    # Остановить docker-compose
    if [ "$DOCKER_STARTED" = true ]; then
        echo -e "   Останавливаю контейнеры..."
        cd "$PROJECT_DIR"
        docker-compose down 2>/dev/null || true
        echo -e "   ${GREEN}✅ Docker контейнеры остановлены${NC}"
    fi

    # Остановить cloudflared
    if [ -n "$TUNNEL_PID" ] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
        kill "$TUNNEL_PID" 2>/dev/null
        wait "$TUNNEL_PID" 2>/dev/null
        echo -e "   ${GREEN}✅ Cloudflare tunnel остановлен${NC}"
    fi

    # Очистить MINIAPP_URL в .env
    if [ -f "$ENV_FILE" ]; then
        if grep -q "^MINIAPP_URL=" "$ENV_FILE"; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' 's|^MINIAPP_URL=.*|MINIAPP_URL=|' "$ENV_FILE"
            else
                sed -i 's|^MINIAPP_URL=.*|MINIAPP_URL=|' "$ENV_FILE"
            fi
            echo -e "   ${GREEN}✅ MINIAPP_URL очищен в .env${NC}"
        fi
    fi

    rm -f "$TUNNEL_LOG"
    echo -e "${GREEN}✅ Готово. До встречи!${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# ============================================================
# Проверки
# ============================================================
echo -e "${BOLD}${BLUE}🚀 Запуск Mini App + Bot с Cloudflare Tunnel${NC}"
echo ""

cd "$PROJECT_DIR"

# Проверка cloudflared
if ! command -v cloudflared &>/dev/null; then
    echo -e "${RED}❌ cloudflared не найден${NC}"
    echo ""
    echo "Установите:"
    echo -e "  ${CYAN}brew install cloudflared${NC}    # macOS"
    echo -e "  ${CYAN}sudo apt install cloudflared${NC} # Ubuntu/Debian"
    exit 1
fi
echo -e "${GREEN}✅ cloudflared${NC}"

# Проверка docker
if ! command -v docker &>/dev/null || ! command -v docker-compose &>/dev/null; then
    echo -e "${RED}❌ docker / docker-compose не найдены${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker + docker-compose${NC}"

# Проверка .env
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ .env не найден${NC}"
    exit 1
fi
echo -e "${GREEN}✅ .env${NC}"

# Получить порт из .env (без source, чтобы не ломаться на спецсимволах)
MINIAPP_PORT=$(grep -E '^MINIAPP_PORT=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d'=' -f2 | tr -d ' "'"'")
MINIAPP_PORT="${MINIAPP_PORT:-8080}"

echo ""

# ============================================================
# 1. Запуск Cloudflare Tunnel
# ============================================================
echo -e "${BLUE}🔒 Запускаю Cloudflare Tunnel → localhost:${MINIAPP_PORT}...${NC}"

cloudflared tunnel --url "http://localhost:$MINIAPP_PORT" \
    --no-autoupdate \
    2>"$TUNNEL_LOG" &
TUNNEL_PID=$!

# Ждём URL (до 15 секунд)
TUNNEL_URL=""
for i in $(seq 1 30); do
    sleep 0.5

    if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
        echo -e "${RED}❌ cloudflared завершился неожиданно:${NC}"
        cat "$TUNNEL_LOG"
        exit 1
    fi

    TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9_-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
done

if [ -z "$TUNNEL_URL" ]; then
    echo -e "${RED}❌ Не удалось получить URL туннеля за 15 секунд${NC}"
    cat "$TUNNEL_LOG"
    exit 1
fi

echo -e "${GREEN}✅ Tunnel: ${BOLD}$TUNNEL_URL${NC}"
echo ""

# ============================================================
# 2. Записать MINIAPP_URL в .env
# ============================================================
if grep -q "^MINIAPP_URL=" "$ENV_FILE"; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^MINIAPP_URL=.*|MINIAPP_URL=$TUNNEL_URL|" "$ENV_FILE"
    else
        sed -i "s|^MINIAPP_URL=.*|MINIAPP_URL=$TUNNEL_URL|" "$ENV_FILE"
    fi
else
    echo "" >> "$ENV_FILE"
    echo "# Mini App URL (auto-set by dev_miniapp.sh)" >> "$ENV_FILE"
    echo "MINIAPP_URL=$TUNNEL_URL" >> "$ENV_FILE"
fi
echo -e "${GREEN}✅ MINIAPP_URL=$TUNNEL_URL → .env${NC}"

# ============================================================
# 3. Запуск docker-compose (если не --tunnel-only)
# ============================================================
if [ "$TUNNEL_ONLY" = true ]; then
    echo ""
    echo -e "${YELLOW}⚡ Режим --tunnel-only: Docker не запускается${NC}"
    echo -e "   Перезапустите бота, чтобы он подхватил новый MINIAPP_URL:"
    echo -e "   ${CYAN}docker-compose restart bot${NC}"
else
    echo ""

    if [ "$NO_BUILD" = true ]; then
        echo -e "${BLUE}🐳 Запускаю docker-compose up (без пересборки)...${NC}"
        docker-compose up -d
    else
        echo -e "${BLUE}🐳 Запускаю docker-compose up --build...${NC}"
        docker-compose up -d --build
    fi

    DOCKER_STARTED=true
    echo -e "${GREEN}✅ Контейнеры запущены${NC}"
fi

# ============================================================
# Итог
# ============================================================
echo ""
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  🎉 Всё запущено!${NC}"
echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}🌐 Mini App URL:${NC}  ${BOLD}$TUNNEL_URL${NC}"
echo -e "  ${CYAN}🏠 Local:${NC}         http://localhost:$MINIAPP_PORT"
echo ""
if [ "$DOCKER_STARTED" = true ]; then
    echo -e "  ${CYAN}📋 Логи бота:${NC}     docker-compose logs -f bot"
    echo -e "  ${CYAN}📋 Логи miniapp:${NC}  docker-compose logs -f miniapp"
fi
echo ""
echo -e "  ${YELLOW}Нажмите Ctrl+C для остановки всего${NC}"
echo ""

# ============================================================
# Показываем логи и ждём Ctrl+C
# ============================================================
if [ "$DOCKER_STARTED" = true ]; then
    # Следим за логами контейнеров
    docker-compose logs -f bot miniapp 2>/dev/null || wait
else
    # Просто ждём
    wait
fi
