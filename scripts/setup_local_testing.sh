#!/bin/bash

# Скрипт для настройки локального тестирования бота

set -e

echo "🚀 Настройка локального тестирования Telegram Knowledge Base Bot"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден${NC}"
    echo "Создайте файл .env на основе .env.example"
    echo ""
    echo "Пример команды:"
    echo "  cp .env.example .env"
    echo "  # Затем отредактируйте .env и заполните необходимые параметры"
    exit 1
fi

echo -e "${GREEN}✅ Файл .env найден${NC}"

# Создание необходимых директорий
echo ""
echo "📁 Создание необходимых директорий..."

mkdir -p local_kb
mkdir -p logs

echo -e "${GREEN}✅ Директории созданы${NC}"

# Проверка NextCloud клиента (опционально)
echo ""
echo "🔍 Проверка NextCloud клиента..."

if command -v nextcloudcmd &> /dev/null; then
    echo -e "${GREEN}✅ NextCloud CLI найден${NC}"
elif command -v nextcloud &> /dev/null; then
    echo -e "${YELLOW}⚠️  NextCloud GUI клиент найден (рекомендуется для Mac)${NC}"
    echo "   Для синхронизации используйте GUI клиент"
else
    echo -e "${YELLOW}⚠️  NextCloud клиент не найден${NC}"
    echo "   Для Mac: brew install --cask nextcloud"
    echo "   Для Linux: установите nextcloud-client или используйте WebDAV"
fi

# Проверка Docker
echo ""
echo "🔍 Проверка Docker..."

if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✅ Docker и Docker Compose найдены${NC}"
    
    # Проверка, запущен ли контейнер
    if docker ps | grep -q knowledge-base-bot; then
        echo -e "${YELLOW}⚠️  Контейнер бота уже запущен${NC}"
    else
        echo "Контейнер бота не запущен"
    fi
else
    echo -e "${RED}❌ Docker или Docker Compose не найдены${NC}"
    echo "   Установите Docker Desktop для Mac: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Проверка переменных окружения
echo ""
echo "🔍 Проверка обязательных переменных окружения..."

source .env

MISSING_VARS=()

if [ -z "$TELEGRAM_TOKEN" ]; then
    MISSING_VARS+=("TELEGRAM_TOKEN")
fi

if [ -z "$CURSOR_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    MISSING_VARS+=("CURSOR_API_KEY или OPENAI_API_KEY")
fi

if [ -n "$MISSING_VARS" ]; then
    echo -e "${RED}❌ Отсутствуют обязательные переменные:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Заполните их в файле .env"
    exit 1
fi

echo -e "${GREEN}✅ Обязательные переменные настроены${NC}"

# Инструкции по NextCloud
echo ""
echo "📋 Инструкции по настройке NextCloud:"
echo ""
echo "1. Создайте пользователя в NextCloud:"
echo "   - Имя: telegram_knowledge_bot (или другое)"
echo "   - Создайте App Password в настройках безопасности"
echo ""
echo "2. Создайте папку KnowledgeBase в NextCloud"
echo ""
echo "3. Настройте синхронизацию:"
echo "   - Для Mac: используйте NextCloud GUI клиент"
echo "   - Синхронизируйте папку KnowledgeBase в ~/NextCloud/KnowledgeBase"
echo "   - Или укажите путь в LOCAL_KB_PATH в .env"
echo ""
echo "4. Заполните в .env:"
echo "   - NEXTCLOUD_URL"
echo "   - NEXTCLOUD_BOT_USERNAME"
echo "   - NEXTCLOUD_BOT_PASSWORD (App Password)"
echo "   - NEXTCLOUD_KNOWLEDGE_BASE_PATH"
echo "   - LOCAL_KB_PATH (путь к локальной копии)"
echo ""

# Проверка пути к локальной БЗ
if [ -n "$LOCAL_KB_PATH" ]; then
    if [ -d "$LOCAL_KB_PATH" ]; then
        echo -e "${GREEN}✅ Локальная БЗ найдена: $LOCAL_KB_PATH${NC}"
    else
        echo -e "${YELLOW}⚠️  Локальная БЗ не найдена: $LOCAL_KB_PATH${NC}"
        echo "   Создайте директорию или настройте синхронизацию с NextCloud"
    fi
else
    echo -e "${YELLOW}⚠️  LOCAL_KB_PATH не установлен${NC}"
    echo "   Установите путь к локальной копии базы знаний в .env"
fi

# Финальные инструкции
echo ""
echo -e "${GREEN}✅ Настройка завершена!${NC}"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Заполните все переменные в .env (см. инструкции выше)"
echo ""
echo "2. Настройте синхронизацию с NextCloud (если нужно)"
echo ""
echo "3. Запустите бота:"
echo "   docker-compose up -d"
echo ""
echo "4. Проверьте логи:"
echo "   docker-compose logs -f bot"
echo ""
echo "5. Отправьте /start боту в Telegram для проверки"
echo ""
echo "📚 Подробная документация: docs/SETUP_NEXTCLOUD.md"

