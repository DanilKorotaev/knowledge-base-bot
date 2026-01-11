# Настройка NextCloud для Telegram Knowledge Base Bot

## Обзор

Эта инструкция описывает настройку NextCloud для работы с ботом. Рекомендуется создать отдельного пользователя для бота с собственной папкой базы знаний.

## Шаг 1: Создание пользователя в NextCloud

### 1.1. Создание нового пользователя

1. Войдите в NextCloud как администратор
2. Перейдите в **Настройки** → **Пользователи** (или `https://your-nextcloud.com/settings/users`)
3. Нажмите **Добавить пользователя**
4. Заполните форму:
   - **Имя пользователя**: `telegram_knowledge_bot` (или другое имя)
   - **Пароль**: сгенерируйте надежный пароль (сохраните его!)
   - **Группы**: можно добавить в группу или оставить без группы
5. Нажмите **Создать**

### 1.2. Создание App Password

Для безопасности рекомендуется использовать App Password вместо основного пароля:

1. Войдите в NextCloud под пользователем `telegram_knowledge_bot`
2. Перейдите в **Настройки** → **Безопасность**
3. Найдите раздел **Устройства и сессии**
4. Нажмите **Создать новый пароль приложения**
5. Введите название: `Telegram Knowledge Base Bot`
6. Скопируйте сгенерированный пароль (он показывается только один раз!)

**Важно:** Сохраните этот пароль в безопасном месте. Он будет использоваться в `.env` файле.

## Шаг 2: Настройка доступа к папке базы знаний

У вас есть два варианта:

### Вариант A: Расшаривание существующей папки (рекомендуется)

Если у вас уже есть папка `KnowledgeBase` в вашей админской учетке:

1. Войдите в NextCloud как **администратор** (ваша учетка)
2. Откройте папку **KnowledgeBase**
3. Нажмите на иконку **Поделиться** (Share) рядом с папкой
4. В поле "Поделиться с пользователем или группой" введите: `telegram_knowledge_bot`
5. Выберите права доступа:
   - ✅ **Редактирование** (чтение и запись) - для работы бота
   - ❌ **Удаление** - можно отключить, если не хотите, чтобы бот удалял файлы
6. Нажмите **Поделиться**

**Преимущества:**
- ✅ Бот работает с вашей папкой, не создает дубликаты
- ✅ Все изменения видны вам сразу
- ✅ Можно контролировать права доступа

**Проверка:**
- Войдите под пользователем `telegram_knowledge_bot`
- Вы должны увидеть расшаренную папку **KnowledgeBase** в списке файлов
- Папка будет отмечена как "Shared with you" (Поделено с вами)

### Вариант B: Создание отдельной папки для бота

Если вы хотите, чтобы у бота была своя папка:

1. Войдите в NextCloud под пользователем `telegram_knowledge_bot`
2. Создайте новую папку: **KnowledgeBase** (или другое имя)
3. Эта папка будет использоваться ботом для хранения базы знаний

**Недостатки:**
- ❌ Дублирование данных
- ❌ Изменения бота не видны в вашей папке
- ❌ Нужна синхронизация между папками

**Подробнее о расшаривании см. [SETUP_NEXTCLOUD_SCENARIO.md](SETUP_NEXTCLOUD_SCENARIO.md)**

## Шаг 3: Локальная синхронизация для тестирования

### 3.1. Использование NextCloud клиента (рекомендуется для Mac)

1. Установите NextCloud клиент:
   ```bash
   brew install --cask nextcloud
   ```

2. **Если используете расшаривание (Вариант A):**
   - Запустите NextCloud клиент
   - Добавьте **второй аккаунт** в клиенте:
     - Нажмите на иконку аккаунта (вверху)
     - **Добавить аккаунт**
     - URL: `https://your-nextcloud.com`
     - Логин: `telegram_knowledge_bot`
     - Пароль: App Password, созданный ранее
   - Синхронизируйте расшаренную папку **KnowledgeBase** → `~/NextCloud-Bot/KnowledgeBase`
   - Локальная копия будет в: `~/NextCloud-Bot/KnowledgeBase`

3. **Если создали отдельную папку (Вариант B):**
   - Запустите NextCloud клиент и подключитесь:
     - **URL сервера**: `https://your-nextcloud.com`
     - **Логин**: `telegram_knowledge_bot`
     - **Пароль**: App Password, созданный ранее
   - Настройте синхронизацию:
     - Выберите папку для синхронизации (например, `~/NextCloud-Bot`)
     - Выберите папку **KnowledgeBase** для синхронизации
     - Дождитесь завершения первоначальной синхронизации
   - Локальная копия будет в: `~/NextCloud-Bot/KnowledgeBase`

**Важно:** Для локальной разработки рекомендуется использовать отдельную папку для бота, чтобы не было конфликтов с вашей основной копией.

### 3.2. Использование WebDAV (альтернатива)

Если не хотите устанавливать клиент, можно использовать WebDAV напрямую:

```bash
# Установить davfs2 (для монтирования WebDAV)
brew install davfs2

# Создать точку монтирования
mkdir -p ~/nextcloud-kb

# Монтировать WebDAV
mount_webdav https://your-nextcloud.com/remote.php/dav/files/telegram_knowledge_bot/KnowledgeBase \
  ~/nextcloud-kb \
  -o username=telegram_knowledge_bot,password=APP_PASSWORD
```

## Шаг 4: Настройка бота

### 4.1. Создание .env файла

Создайте файл `.env` в корне проекта:

```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token

# Cursor CLI / OpenAI API
CURSOR_API_KEY=your_cursor_api_key
# ИЛИ
OPENAI_API_KEY=your_openai_api_key
CURSOR_MODEL=gpt-4o

# NextCloud
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_BOT_USERNAME=telegram_knowledge_bot
NEXTCLOUD_BOT_PASSWORD=your_app_password_here
NEXTCLOUD_KNOWLEDGE_BASE_PATH=/KnowledgeBase

# Local Knowledge Base
# Для локального тестирования укажите путь к синхронизированной папке
LOCAL_KB_PATH=/Users/your_username/NextCloud/KnowledgeBase
# Или для Docker:
# LOCAL_KB_PATH=/var/knowledge-base-bot/kb

# Синхронизация
ENABLE_SYNC=false  # Отключить для локального тестирования (используется NextCloud клиент)
AUTO_SYNC=false
SYNC_INTERVAL=300

# Database (для локального тестирования используйте SQLite)
DB_TYPE=sqlite
DB_FILE=bot.db
# Или PostgreSQL для Docker:
# DB_TYPE=postgresql
# DB_HOST=postgres
# DB_PORT=5432
# DB_NAME=knowledge_base_bot
# DB_USER=postgres
# DB_PASSWORD=postgres

# Bot settings
LOG_LEVEL=INFO
MAX_SESSION_MESSAGES=50
MAX_ATTACHMENTS_PER_MESSAGE=5
ENABLE_CHANGE_TRACKING=true
```

### 4.2. Для Docker

Если используете Docker, путь к локальной БЗ должен быть внутри контейнера:

```bash
# В docker-compose.yml уже настроено:
# volumes:
#   - ./local_kb:/var/knowledge-base-bot/kb

# В .env для Docker:
LOCAL_KB_PATH=/var/knowledge-base-bot/kb
```

И создайте локальную папку для синхронизации:

```bash
mkdir -p ./local_kb
```

## Шаг 5: Первоначальная синхронизация

### 5.1. Если используете NextCloud клиент

1. Убедитесь, что папка `KnowledgeBase` синхронизирована
2. Скопируйте содержимое в `./local_kb` (для Docker) или используйте путь к синхронизированной папке

### 5.2. Если используете WebDAV напрямую

Можно использовать скрипт для первоначальной синхронизации (см. `scripts/sync_from_nextcloud.sh`)

## Шаг 6: Проверка настройки

1. Запустите бота:
   ```bash
   # Локально
   python bot.py
   
   # Или через Docker
   docker-compose up -d
   ```

2. Проверьте логи:
   ```bash
   docker-compose logs -f bot
   ```

3. Отправьте тестовое сообщение боту в Telegram

4. Проверьте, что файлы создаются/изменяются в локальной папке

5. Проверьте синхронизацию с NextCloud (если включена)

## Рекомендации для продакшена

### На сервере

1. Используйте отдельного пользователя NextCloud (как описано выше)
2. Настройте автоматическую синхронизацию через `nextcloudcmd` или WebDAV API
3. Используйте PostgreSQL вместо SQLite
4. Настройте регулярные бэкапы базы данных
5. Используйте App Password для безопасности

### Безопасность

- ✅ Используйте App Password вместо основного пароля
- ✅ Ограничьте права доступа пользователя бота только к нужной папке
- ✅ Регулярно обновляйте пароли
- ✅ Используйте HTTPS для NextCloud
- ✅ Настройте firewall на сервере

## Устранение проблем

### Проблема: Бот не может подключиться к NextCloud

**Решение:**
1. Проверьте URL NextCloud (должен быть доступен)
2. Проверьте логин и пароль (используйте App Password)
3. Проверьте путь к папке (`NEXTCLOUD_KNOWLEDGE_BASE_PATH`)
4. Проверьте права доступа пользователя

### Проблема: Файлы не синхронизируются

**Решение:**
1. Проверьте, что `ENABLE_SYNC=true` в `.env`
2. Проверьте логи бота на ошибки синхронизации
3. Убедитесь, что NextCloud доступен из контейнера/сервера
4. Проверьте права доступа к папке

### Проблема: Docker не видит локальные файлы

**Решение:**
1. Проверьте, что volume правильно настроен в `docker-compose.yml`
2. Проверьте права доступа к папке `./local_kb`
3. Убедитесь, что путь в `.env` соответствует пути в контейнере

## Дополнительные ресурсы

- [Документация NextCloud](https://docs.nextcloud.com/)
- [NextCloud WebDAV API](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/index.html)
- [Настройка App Passwords](https://docs.nextcloud.com/server/latest/user_manual/en/user_2fa.html#app-passwords)

