# Инструкции по установке и настройке

## Требования

- Python 3.11+
- PostgreSQL (или SQLite для локальной разработки)
- Cursor CLI (или OpenAI API ключ)
- NextCloud (опционально, для синхронизации)

## Установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/DanilKorotaev/knowledge-base-bot.git
cd knowledge-base-bot
```

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните необходимые параметры:

```bash
cp .env.example .env
```

**Обязательные параметры:**
- `TELEGRAM_TOKEN` - токен Telegram бота
- `CURSOR_API_KEY` или `OPENAI_API_KEY` - API ключ для работы с AI
- `OPENAI_API_KEY` - для транскрибации голосовых (Whisper)

**Для работы с базой данных:**
- PostgreSQL: `DB_TYPE=postgresql`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- SQLite (локальная разработка): `DB_TYPE=sqlite`, `DB_FILE=bot.db`

**Для синхронизации с NextCloud (опционально):**
- `NEXTCLOUD_URL` - URL вашего NextCloud
- `NEXTCLOUD_BOT_USERNAME` - имя пользователя бота в NextCloud
- `NEXTCLOUD_BOT_PASSWORD` - App Password для бота
- `NEXTCLOUD_KNOWLEDGE_BASE_PATH` - путь к базе знаний в NextCloud

**Для локальной копии базы знаний:**
- `LOCAL_KB_PATH` - путь к локальной копии базы знаний
- `ENABLE_SYNC` - включить/выключить синхронизацию с NextCloud

### 4. Инициализация базы данных

При первом запуске бота база данных будет автоматически инициализирована.

### 5. Запуск бота

```bash
python bot.py
```

## Локальная разработка

Для локальной разработки используйте SQLite:

```bash
# В .env
DB_TYPE=sqlite
DB_FILE=bot.db
ENABLE_SYNC=false
LOCAL_KB_PATH=/path/to/your/local/knowledge-base
```

## Настройка Cursor CLI

1. Установите Cursor CLI:
```bash
curl https://cursor.com/install -fsS | bash
export PATH="$HOME/.local/bin:$PATH"
```

2. Получите API ключ:
- Перейдите в https://cursor.com/settings
- Integrations → User API Keys → Generate new key
- Установите в `.env` как `CURSOR_API_KEY`

## Настройка NextCloud

1. Создайте пользователя `telegram_knowledge_bot` в NextCloud
2. Настройте права доступа к папке KnowledgeBase (чтение, запись)
3. Создайте App Password для бота
4. Установите параметры в `.env`

## Проверка работы

После запуска бота отправьте `/start` в Telegram для проверки работы.

