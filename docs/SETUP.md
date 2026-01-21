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

**Для управления доступом:**
- `ACCESS_MODE` - режим доступа: `open` (открытый, все имеют доступ) или `restricted` (ограниченный, только whitelist). По умолчанию: `restricted`
- `ADMIN_TELEGRAM_IDS` - список Telegram ID администраторов через запятую (например: `123456789,987654321`). Администраторы автоматически получают доступ при первом запуске

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

## Управление доступом

Бот поддерживает два режима доступа:

### Открытый режим (`ACCESS_MODE=open`)
Все пользователи имеют доступ к боту. Используйте этот режим для публичных ботов.

### Ограниченный режим (`ACCESS_MODE=restricted`) - по умолчанию
Только пользователи из whitelist имеют доступ. Новые пользователи должны быть явно добавлены администратором.

### Административные команды

Администраторы могут управлять доступом через следующие команды:

- `/admin_allow <telegram_id>` - разрешить доступ пользователю
- `/admin_disallow <telegram_id>` - запретить доступ пользователю
- `/admin_list` - показать список всех разрешенных пользователей
- `/admin_set_admin <telegram_id>` - назначить пользователя администратором
- `/admin_remove_admin <telegram_id>` - убрать права администратора

### Настройка администраторов

1. Узнайте свой Telegram ID (можно использовать бота @userinfobot)
2. Установите переменную окружения `ADMIN_TELEGRAM_IDS`:
   ```bash
   ADMIN_TELEGRAM_IDS=123456789,987654321
   ```
3. При первом запуске бота администраторы автоматически получат доступ и права администратора

### Пример настройки

```bash
# В .env файле
ACCESS_MODE=restricted
ADMIN_TELEGRAM_IDS=123456789
```

## Проверка работы

После запуска бота отправьте `/start` в Telegram для проверки работы.

В режиме `restricted` неавторизованные пользователи увидят сообщение об отказе в доступе и должны обратиться к администратору.

