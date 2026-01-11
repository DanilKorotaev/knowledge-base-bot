# Быстрый старт с Docker

Краткая инструкция для локального тестирования бота через Docker.

## Предварительные требования

1. **Docker Desktop** установлен и запущен
2. **NextCloud** доступен (локально или удаленно)
3. **Telegram Bot Token** (получить у [@BotFather](https://t.me/BotFather))
4. **Cursor API Key** или **OpenAI API Key**

## Шаг 1: Настройка NextCloud

### 1.1. Создание пользователя для бота

1. Войдите в NextCloud как администратор
2. **Настройки** → **Пользователи** → **Добавить пользователя**
3. Создайте пользователя: `telegram_knowledge_bot`
4. **Настройки** → **Безопасность** → **Создать новый пароль приложения**
5. Сохраните App Password (понадобится для `.env`)

### 1.2. Создание папки базы знаний

1. Войдите под пользователем `telegram_knowledge_bot`
2. Создайте папку: **KnowledgeBase**

### 1.3. Синхронизация на Mac (через NextCloud клиент)

```bash
# Установить NextCloud клиент
brew install --cask nextcloud

# Запустить и подключиться:
# - URL: https://your-nextcloud.com
# - Логин: telegram_knowledge_bot
# - Пароль: App Password
# - Синхронизировать папку KnowledgeBase в ~/NextCloud/KnowledgeBase
```

## Шаг 2: Настройка проекта

### 2.1. Клонирование и настройка

```bash
git clone https://github.com/DanilKorotaev/knowledge-base-bot.git
cd knowledge-base-bot

# Создать .env файл
cp .env.example .env
```

### 2.2. Заполнение .env

Откройте `.env` и заполните:

```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token

# Cursor / OpenAI
CURSOR_API_KEY=your_cursor_api_key
# ИЛИ
OPENAI_API_KEY=your_openai_api_key

# NextCloud
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_BOT_USERNAME=telegram_knowledge_bot
NEXTCLOUD_BOT_PASSWORD=your_app_password_here
NEXTCLOUD_KNOWLEDGE_BASE_PATH=/KnowledgeBase

# Local Knowledge Base
# Для Docker используйте путь внутри контейнера:
LOCAL_KB_PATH=/var/knowledge-base-bot/kb

# Database (для Docker используйте PostgreSQL)
DB_TYPE=postgresql
DB_HOST=postgres
DB_PORT=5432
DB_NAME=knowledge_base_bot
DB_USER=postgres
DB_PASSWORD=postgres

# Синхронизация (отключить для локального тестирования)
ENABLE_SYNC=false
```

### 2.3. Настройка локальной копии БЗ

**Вариант A: Использовать NextCloud клиент (рекомендуется)**

```bash
# Создать директорию для Docker volume
mkdir -p local_kb

# Скопировать содержимое из синхронизированной папки
cp -r ~/NextCloud/KnowledgeBase/* local_kb/
```

**Вариант B: Пустая директория (для тестирования)**

```bash
mkdir -p local_kb
# Бот создаст необходимую структуру при первом запуске
```

## Шаг 3: Запуск

### 3.1. Запуск скрипта настройки (опционально)

```bash
./scripts/setup_local_testing.sh
```

### 3.2. Запуск бота

```bash
docker-compose up -d
```

### 3.3. Проверка логов

```bash
docker-compose logs -f bot
```

## Шаг 4: Тестирование

1. Откройте Telegram и найдите вашего бота
2. Отправьте `/start`
3. Отправьте текстовое сообщение (например: "Привет!")
4. Проверьте, что бот отвечает

## Полезные команды

```bash
# Остановить бота
docker-compose down

# Перезапустить бота
docker-compose restart bot

# Просмотр логов
docker-compose logs -f bot

# Войти в контейнер
docker exec -it knowledge-base-bot bash

# Очистить все (включая БД)
docker-compose down -v
```

## Устранение проблем

### Бот не запускается

```bash
# Проверьте логи
docker-compose logs bot

# Проверьте .env файл
cat .env | grep -v PASSWORD
```

### Бот не может подключиться к NextCloud

1. Проверьте `NEXTCLOUD_URL` (должен быть доступен)
2. Проверьте `NEXTCLOUD_BOT_USERNAME` и `NEXTCLOUD_BOT_PASSWORD`
3. Убедитесь, что используете App Password, а не основной пароль

### Файлы не видны в контейнере

1. Проверьте volume в `docker-compose.yml`:
   ```yaml
   volumes:
     - ./local_kb:/var/knowledge-base-bot/kb
   ```
2. Проверьте права доступа:
   ```bash
   ls -la local_kb
   ```

## Следующие шаги

- Подробная настройка NextCloud: [SETUP_NEXTCLOUD.md](SETUP_NEXTCLOUD.md)
- Полная документация: [SETUP.md](SETUP.md)
- Разработка: [DEVELOPMENT.md](DEVELOPMENT.md)

