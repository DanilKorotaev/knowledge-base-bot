# Развёртывание на сервере (с уже работающим NextCloud)

Пошаговая инструкция по развёртыванию Telegram Knowledge Base Bot на сервере, где уже установлен и работает NextCloud с базой знаний.

Два поддомена, один сервер:
- `nextcloud.example.ru` — NextCloud (уже работает)
- `knowledgebotminiapp.example.ru` — Telegram Mini App (отдельный поддомен, HTTPS)

Бот (Telegram polling) работает без внешних портов.

---

## Предварительные требования

| Компонент | Требование |
|-----------|-----------|
| **ОС** | Linux (Ubuntu 22.04+ / Debian 12+ рекомендуется) |
| **Docker** | Docker Engine 24+ и Docker Compose v2 |
| **Nginx** | Установлен на хосте (reverse proxy) |
| **NextCloud** | Уже работает на этом же сервере за Nginx с HTTPS |
| **SSL-сертификат** | Уже есть для NextCloud; для Mini App нужен отдельный или wildcard |
| **DNS** | A-запись для `knowledgebotminiapp.example.ru` → IP сервера |
| **Telegram Bot Token** | Получить у [@BotFather](https://t.me/BotFather) |
| **Cursor API Key** | Или OpenAI API Key |
| **RAM** | Минимум 1 ГБ свободной памяти для бота + БД |

### Что мы получим

```
https://nextcloud.example.ru           → NextCloud (как было)
https://knowledgebotminiapp.example.ru → Telegram Mini App (HTTPS)
Telegram Bot                            → polling, без внешних портов
```

---

## Шаг 1: Подготовка NextCloud

Поскольку NextCloud уже работает на сервере, нужно создать отдельного пользователя для бота.

### 1.1. Создание пользователя для бота

1. Войдите в NextCloud как **администратор**
2. **Настройки** → **Пользователи** → **Добавить пользователя**
3. Заполните:
   - **Имя пользователя**: `telegram_knowledge_bot`
   - **Пароль**: сгенерируйте надёжный пароль
4. Нажмите **Создать**

### 1.2. Расшаривание папки базы знаний

1. Войдите в NextCloud как **администратор** (ваша основная учётка)
2. Найдите папку **KnowledgeBase** (или как она у вас называется)
3. Нажмите **Поделиться** → введите `telegram_knowledge_bot`
4. Дайте права:
   - ✅ **Редактирование** (чтение и запись)
   - ⚠️ **Удаление** — по желанию (можно отключить для безопасности)
5. Нажмите **Поделиться**

### 1.3. Создание App Password

1. Войдите под `telegram_knowledge_bot`
2. **Настройки** → **Безопасность** → **Устройства и сессии**
3. **Создать новый пароль приложения** → название: `Telegram KB Bot`
4. **Сохраните пароль** (показывается только один раз!)

### 1.4. Проверка доступа

```bash
# Проверить WebDAV-доступ (замените значения на свои)
curl -u "telegram_knowledge_bot:APP_PASSWORD" \
  "https://nextcloud.example.ru/remote.php/dav/files/telegram_knowledge_bot/KnowledgeBase/" \
  -X PROPFIND -H "Depth: 1" | head -50
```

---

## Шаг 2: Клонирование проекта

```bash
# Выбрать директорию для проекта
cd /opt  # или /home/your_user/
git clone https://github.com/DanilKorotaev/knowledge-base-bot.git
cd knowledge-base-bot
```

---

## Шаг 3: Создание .env файла

```bash
nano .env
```

Заполните (шаблон ниже):

```bash
# ============================================
# Telegram
# ============================================
TELEGRAM_TOKEN=your_telegram_bot_token_here

# ============================================
# AI Engine (нужен хотя бы один)
# ============================================
# Cursor CLI API ключ (рекомендуется)
CURSOR_API_KEY=your_cursor_api_key_here
# Или OpenAI API ключ (нужен для Whisper транскрипции голосовых)
OPENAI_API_KEY=your_openai_api_key_here
# Модель: "auto" = автовыбор, или конкретная (gpt-4o, claude-sonnet, etc.)
CURSOR_MODEL=auto

# ============================================
# NextCloud
# ============================================
# URL NextCloud (ваш существующий поддомен)
NEXTCLOUD_URL=https://nextcloud.example.ru
NEXTCLOUD_BOT_USERNAME=telegram_knowledge_bot
NEXTCLOUD_BOT_PASSWORD=your_app_password_here
NEXTCLOUD_KNOWLEDGE_BASE_PATH=/KnowledgeBase

# Ссылки на файлы в ответах бота (опционально)
NEXTCLOUD_WEB_URL=https://nextcloud.example.ru
# NEXTCLOUD_LINK_MODE=disabled  # "share" | "direct" | "disabled"

# ============================================
# Локальная копия базы знаний
# ============================================
LOCAL_KB_PATH=/var/knowledge-base-bot/kb

# ============================================
# Синхронизация с NextCloud
# ============================================
ENABLE_SYNC=true
AUTO_SYNC=true
SYNC_INTERVAL=300
SYNC_DELETE_MISSING=true

# ============================================
# Database (PostgreSQL — рекомендуется для продакшена)
# ============================================
DB_TYPE=postgresql
DB_HOST=postgres
DB_PORT=5432
DB_NAME=knowledge_base_bot
DB_USER=postgres
DB_PASSWORD=СГЕНЕРИРУЙТЕ_НАДЁЖНЫЙ_ПАРОЛЬ

# ============================================
# Настройки бота
# ============================================
LOG_LEVEL=INFO
MAX_SESSION_MESSAGES=50
MAX_ATTACHMENTS_PER_MESSAGE=5
ENABLE_CHANGE_TRACKING=true

# ============================================
# Стриминг ответов
# ============================================
STREAMING_ENABLED=true
STREAMING_UPDATE_INTERVAL=1.5
STREAMING_MIN_BUFFER=100

# ============================================
# Транскрипция голосовых
# ============================================
TRANSCRIPTION_POLISH_ENABLED=true
TRANSCRIPTION_POLISH_MODEL=auto

# ============================================
# Контроль доступа
# ============================================
ACCESS_MODE=restricted
# Telegram ID администраторов (через запятую)
ADMIN_TELEGRAM_IDS=YOUR_TELEGRAM_ID

# ============================================
# Mini App (Telegram Web App)
# ============================================
# HTTPS URL Mini App на отдельном поддомене
MINIAPP_URL=https://knowledgebotminiapp.example.ru
MINIAPP_PORT=8080

# CORS (опционально, по умолчанию "*")
# MINIAPP_CORS_ORIGINS=https://knowledgebotminiapp.example.ru
```

### Важно: NEXTCLOUD_URL — только внешний домен

Бот работает **внутри Docker-контейнера**, но `NEXTCLOUD_URL` **обязательно** должен быть вашим внешним доменом:

```bash
NEXTCLOUD_URL=https://nextcloud.example.ru
```

**Почему нельзя использовать внутренний Docker URL?** Бот генерирует кликабельные ссылки на файлы в NextCloud (при `NEXTCLOUD_LINK_MODE=share` или `direct`) и отправляет их пользователю в Telegram. Эти ссылки строятся на основе `NEXTCLOUD_URL` (или `NEXTCLOUD_WEB_URL`). Если указать внутренний адрес (`http://nextcloud:80` или `http://172.17.0.1:PORT`), ссылки будут нерабочими — пользователь не сможет открыть их в браузере.

Путь: Бот из контейнера → внешний URL → Nginx → NextCloud. Это работает надёжно.

---

## Шаг 4: Настройка DNS

Создайте **A-запись** для поддомена Mini App у вашего DNS-провайдера:

```
knowledgebotminiapp.example.ru  →  IP_ВАШЕГО_СЕРВЕРА
```

Проверьте, что DNS-запись распространилась:

```bash
dig knowledgebotminiapp.example.ru +short
# Должен вернуть IP вашего сервера
```

---

## Шаг 5: Настройка SSL-сертификата для Mini App

Mini App работает на отдельном поддомене, поэтому ему нужен SSL-сертификат. Есть два варианта.

### Вариант A: Отдельный сертификат Let's Encrypt (рекомендуется)

Самый простой вариант — получить отдельный сертификат для поддомена Mini App:

```bash
# Убедитесь, что certbot установлен
sudo apt install certbot python3-certbot-nginx -y

# Получить сертификат (DNS уже должен быть настроен, шаг 4)
sudo certbot certonly --nginx -d knowledgebotminiapp.example.ru
```

Certbot автоматически обновляет сертификаты.

### Вариант B: Wildcard-сертификат

Если у вас wildcard-сертификат `*.example.ru` — он покроет оба поддомена (`nextcloud.example.ru` и `knowledgebotminiapp.example.ru`). Дополнительных действий не нужно.

Проверить тип текущего сертификата:

```bash
sudo certbot certificates
```

---

## Шаг 6: Настройка Nginx

Nginx уже обслуживает NextCloud. Нужно добавить **отдельный server-блок** для поддомена Mini App.

### 6.1. Схема маршрутизации

```
Интернет
   │
   ▼
Nginx (порт 443, SSL)
   ├── nextcloud.example.ru           →  NextCloud          (как было)
   └── knowledgebotminiapp.example.ru →  127.0.0.1:8080     (Mini App)
```

### 6.2. Создание конфига для Mini App

Создайте новый файл конфигурации:

```bash
sudo nano /etc/nginx/sites-available/knowledgebotminiapp.example.ru
```

Содержимое:

```nginx
# HTTP → HTTPS редирект
server {
    listen 80;
    listen [::]:80;
    server_name knowledgebotminiapp.example.ru;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name knowledgebotminiapp.example.ru;

    # SSL-сертификат (путь от certbot, шаг 5)
    ssl_certificate /etc/letsencrypt/live/knowledgebotminiapp.example.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/knowledgebotminiapp.example.ru/privkey.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Проксирование всех запросов в контейнер Mini App
    location / {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket (на будущее)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Таймауты
        proxy_connect_timeout 60s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

> 📁 Готовый конфиг также есть в репозитории: `nginx/miniapp-location.conf`
> 📁 Полный пример с NextCloud: `nginx/example-site.conf`
>
> Если у вас **wildcard-сертификат**, поменяйте пути к сертификату:
> ```nginx
> ssl_certificate /etc/letsencrypt/live/example.ru/fullchain.pem;
> ssl_certificate_key /etc/letsencrypt/live/example.ru/privkey.pem;
> ```

### 6.3. Активация конфига

```bash
# Создать симлинк
sudo ln -s /etc/nginx/sites-available/knowledgebotminiapp.example.ru \
           /etc/nginx/sites-enabled/knowledgebotminiapp.example.ru

# Проверить синтаксис
sudo nginx -t

# Перезагрузить
sudo systemctl reload nginx
```

### 6.4. Проверка

```bash
# NextCloud должен работать как раньше
curl -I https://nextcloud.example.ru/status.php

# Mini App пока вернёт 502 (контейнер ещё не запущен) — это OK
curl -I https://knowledgebotminiapp.example.ru/
```

---

## Шаг 7: Настройка Docker Compose

### 7.1. Продакшен-запуск (рекомендуется)

В репозитории есть `docker-compose.prod.yml` с продакшен-оверрайдами:
- Mini App порт привязан к `127.0.0.1` (не светит наружу, только для Nginx)
- PostgreSQL порт не экспортирован
- Volume для БЗ на серверном пути

```bash
cd /opt/knowledge-base-bot

# Создать директории
mkdir -p logs
sudo mkdir -p /var/lib/knowledge-base-bot/kb

# Запуск с продакшен-оверрайдом
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

> **Совет:** Создайте alias для удобства:
> ```bash
> echo 'alias dc-prod="docker compose -f docker-compose.yml -f docker-compose.prod.yml"' >> ~/.bashrc
> source ~/.bashrc
>
> # Теперь можно:
> dc-prod up -d --build
> dc-prod logs -f bot
> dc-prod ps
> ```

### 7.2. Альтернатива: запуск без prod-оверрайда

Если не хотите использовать `docker-compose.prod.yml`, можно запустить стандартный compose. Но тогда порт Mini App (8080) будет доступен извне напрямую. Nginx всё равно будет работать.

```bash
docker compose up -d --build
```

---

## Шаг 8: Запуск и проверка

### 8.1. Сборка и запуск

```bash
cd /opt/knowledge-base-bot

# С продакшен-оверрайдом:
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Проверить статус
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

### 8.2. Проверка логов

```bash
# Логи бота
docker compose logs -f bot

# Логи Mini App
docker compose logs -f miniapp

# Логи базы данных
docker compose logs -f postgres

# Все логи
docker compose logs -f
```

### 8.3. Первоначальная синхронизация

При первом запуске с `ENABLE_SYNC=true` бот автоматически:
1. Создаст директорию `/var/knowledge-base-bot/kb` (внутри контейнера)
2. Скачает все файлы из NextCloud
3. Запустит периодическую синхронизацию

В логах вы увидите:

```
Синхронизация инициализирована
Локальная папка пуста. Начинаю загрузку из NextCloud...
Найдено файлов для синхронизации: XX
✅ База знаний загружена из NextCloud
```

### 8.4. Проверка всех сервисов

```bash
# 1. NextCloud (должен работать как раньше)
curl -s https://nextcloud.example.ru/status.php | python3 -m json.tool

# 2. Mini App (должен вернуть HTML)
curl -s https://knowledgebotminiapp.example.ru/ | head -5
# Ожидаемый результат: <!DOCTYPE html>...

# 3. Mini App API (должен вернуть JSON с 401)
curl -s https://knowledgebotminiapp.example.ru/api/sessions
# Ожидаемый результат: {"detail":"Отсутствует заголовок X-Telegram-Init-Data"}
# (401 — это правильно, значит API работает и требует авторизации)

# 4. Mini App статика (CSS/JS)
curl -s -o /dev/null -w "%{http_code}" https://knowledgebotminiapp.example.ru/static/css/styles.css
# Ожидаемый результат: 200

# 5. Бот в Telegram
# Откройте бота → /start → проверьте ответ
```

### 8.5. Проверка подключения к NextCloud из контейнера

```bash
# Зайти в контейнер бота
docker exec -it knowledge-base-bot bash

# Проверить доступ к NextCloud
curl -s -u "telegram_knowledge_bot:APP_PASSWORD" \
  "https://nextcloud.example.ru/remote.php/dav/files/telegram_knowledge_bot/" \
  -X PROPFIND -H "Depth: 0" | head -5

# Выйти
exit
```

---

## Шаг 9: Настройка автозапуска

Docker Compose с `restart: unless-stopped` уже обеспечивает автозапуск контейнеров после перезагрузки сервера. Убедитесь, что Docker-демон запускается автоматически:

```bash
sudo systemctl enable docker
```

---

## Обновление

> В примерах ниже используется alias `dc-prod` (см. шаг 7.1). Если не создавали alias, замените на полную команду:
> `docker compose -f docker-compose.yml -f docker-compose.prod.yml`

### Обновление кода

```bash
cd /opt/knowledge-base-bot

# Остановить всё
dc-prod down

# Обновить код
git pull

# Пересобрать и запустить
dc-prod up -d --build

# Проверить логи
dc-prod logs -f bot
```

### Обновление без простоя (пересборка только бота)

```bash
cd /opt/knowledge-base-bot
git pull

# Пересобрать только бот-контейнер (miniapp продолжает работать)
dc-prod build bot
dc-prod up -d bot

dc-prod logs -f bot
```

### Обновление Mini App

```bash
cd /opt/knowledge-base-bot
git pull

dc-prod build miniapp
dc-prod up -d miniapp

# Проверить
curl -s https://knowledgebotminiapp.example.ru/ | head -3
```

---

## Мониторинг

### Логи

```bash
# Последние 100 строк логов бота
docker compose logs --tail=100 bot

# Следить за логами в реальном времени
docker compose logs -f bot

# Логи за последний час
docker compose logs --since="1h" bot
```

### Состояние контейнеров

```bash
docker compose ps
```

### Использование ресурсов

```bash
docker stats knowledge-base-bot knowledge-base-bot-db
```

---

## Бэкапы

### База данных PostgreSQL

```bash
# Создать бэкап
docker exec knowledge-base-bot-db pg_dump -U postgres knowledge_base_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановить из бэкапа
docker exec -i knowledge-base-bot-db psql -U postgres knowledge_base_bot < backup_YYYYMMDD_HHMMSS.sql
```

### Автоматические бэкапы (cron)

```bash
# Добавить в crontab
crontab -e

# Ежедневный бэкап в 3:00
0 3 * * * docker exec knowledge-base-bot-db pg_dump -U postgres knowledge_base_bot > /opt/backups/kb-bot-db-$(date +\%Y\%m\%d).sql 2>/dev/null
```

### Данные базы знаний

База знаний хранится в Docker volume и синхронизируется с NextCloud. Бэкап NextCloud = бэкап БЗ.

```bash
# Но можно сделать и отдельный бэкап volume:
docker run --rm -v knowledge-base-bot_postgres_data:/data -v /opt/backups:/backup \
  alpine tar czf /backup/postgres-data-$(date +%Y%m%d).tar.gz /data
```

---

## Полезные команды

```bash
# Перезапуск бота
dc-prod restart bot

# Перезапуск Mini App
dc-prod restart miniapp

# Зайти в контейнер бота
docker exec -it knowledge-base-bot bash

# Зайти в контейнер Mini App
docker exec -it knowledge-base-bot-miniapp bash

# Посмотреть файлы базы знаний внутри контейнера
docker exec knowledge-base-bot ls -la /var/knowledge-base-bot/kb/

# Проверить, что cursor-agent установлен
docker exec knowledge-base-bot which cursor-agent

# Остановить всё
dc-prod down

# Остановить и удалить данные (⚠️ удалит БД!)
dc-prod down -v

# Пересобрать с нуля (без кэша)
dc-prod build --no-cache
dc-prod up -d

# Логи Nginx (на хосте)
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## Устранение проблем

### Бот не запускается

```bash
# Проверить логи
dc-prod logs bot

# Частые причины:
# - Неправильный TELEGRAM_TOKEN
# - Нет CURSOR_API_KEY и OPENAI_API_KEY
# - Синтаксическая ошибка в .env
```

### NextCloud недоступен из контейнера

```bash
# Проверить с хоста
curl -s https://nextcloud.example.ru/status.php

# Проверить из контейнера бота
docker exec knowledge-base-bot curl -s https://nextcloud.example.ru/status.php
```

### Mini App не открывается в Telegram

**Симптомы:** кнопка «Открыть Mini App» в Telegram не работает или показывает ошибку.

```bash
# 1. Проверить DNS
dig knowledgebotminiapp.example.ru +short
# Должен вернуть IP вашего сервера

# 2. Проверить SSL-сертификат
curl -vI https://knowledgebotminiapp.example.ru/ 2>&1 | grep -E "SSL|subject|expire"

# 3. Проверить, работает ли Mini App через Nginx
curl -s https://knowledgebotminiapp.example.ru/ | head -5
# Должен вернуть: <!DOCTYPE html>...

# 4. Если 502 Bad Gateway — контейнер miniapp не запущен
dc-prod ps miniapp
dc-prod logs miniapp

# 5. Если сайт не открывается — проверить Nginx-конфиг
sudo nginx -t
sudo grep -r "knowledgebotminiapp" /etc/nginx/

# 6. Проверить, что MINIAPP_URL правильный в .env
grep MINIAPP_URL .env
# Должно быть: MINIAPP_URL=https://knowledgebotminiapp.example.ru

# 7. Проверить Mini App API
curl -s https://knowledgebotminiapp.example.ru/api/sessions
# Должен вернуть: {"detail":"Отсутствует заголовок X-Telegram-Init-Data"}
```

### Mini App: статика не загружается (CSS/JS)

Если Mini App открывается, но без стилей / с ошибками в консоли:

```bash
# Проверить, что статика доступна
curl -s -o /dev/null -w "%{http_code}" https://knowledgebotminiapp.example.ru/static/css/styles.css
# Должен вернуть: 200

# Если 404 — проверить логи miniapp-контейнера
dc-prod logs miniapp
```

### cursor-agent не найден

```bash
# Cursor CLI устанавливается при сборке Docker-образа
docker exec knowledge-base-bot which cursor-agent

# Если не установлен — пересоберите образ:
dc-prod build --no-cache bot
dc-prod up -d bot
```

### Проблемы с правами доступа к файлам

```bash
# Проверить владельца volume
docker exec knowledge-base-bot ls -la /var/knowledge-base-bot/

# Если нужно исправить права
docker exec knowledge-base-bot chmod -R 755 /var/knowledge-base-bot/kb/
```

### База данных не инициализируется

```bash
# Проверить логи PostgreSQL
dc-prod logs postgres

# Проверить подключение
docker exec knowledge-base-bot-db pg_isready -U postgres
```

### Nginx: 502 Bad Gateway

```bash
# Контейнер Mini App не запущен или не слушает порт 8080
dc-prod ps
dc-prod logs miniapp

# Проверить, слушает ли порт 8080 на хосте
ss -tlnp | grep 8080
# Или
curl -s http://127.0.0.1:8080/ | head -3
```

---

## Безопасность

### Рекомендации

- ✅ Используйте **App Password** для NextCloud (не основной пароль)
- ✅ Установите `ACCESS_MODE=restricted` и укажите `ADMIN_TELEGRAM_IDS`
- ✅ Используйте надёжный `DB_PASSWORD` (не `postgres`)
- ✅ Ограничьте права пользователя бота в NextCloud
- ✅ Mini App порт (8080) привязан к `127.0.0.1` через `docker-compose.prod.yml` — не светит наружу
- ✅ PostgreSQL не экспортирует порт наружу (через `docker-compose.prod.yml`)
- ✅ Храните `.env` с ограниченными правами: `chmod 600 .env`
- ✅ HTTPS обеспечивается Nginx (отдельный сертификат для каждого поддомена)
- ✅ Mini App аутентификация через Telegram initData (HMAC-SHA256)

### Файрволл

```bash
# Если используете ufw:
sudo ufw allow 22        # SSH
sudo ufw allow 80        # HTTP (редирект на HTTPS)
sudo ufw allow 443       # HTTPS (Nginx: NextCloud + Mini App)

# НЕ открывать:
# - 5432 (PostgreSQL) — доступен только внутри Docker-сети
# - 8080 (Mini App) — доступен только через Nginx (если используете prod-оверрайд)

sudo ufw enable
```

### SSL-сертификаты

Два поддомена — два сертификата (или один wildcard). Убедитесь, что автообновление работает:

```bash
# Проверить автообновление
sudo certbot renew --dry-run

# Если certbot настроен через cron/timer:
sudo systemctl status certbot.timer

# Посмотреть все сертификаты
sudo certbot certificates
```

---

## Архитектура на сервере

```
                          Интернет
                             │
                    ┌────────┴────────┐
                    │   Nginx (443)   │  ← SSL-сертификаты (Let's Encrypt)
                    │  reverse proxy  │
                    └────────┬────────┘
                      │             │
    knowledgebotminiapp   nextcloud.
      .example.ru          example.ru
                      │             │
                      ▼             ▼
        ┌─────────────────┐  ┌──────────────┐
        │  Mini App       │  │  NextCloud   │
        │  (FastAPI)      │  │  (уже работ.)│
        │  127.0.0.1:8080 │  │              │
        └────────┬────────┘  └──────┬───────┘
                 │                   │
        ┌────────┴───────────────────┘
        │   bot-network (Docker)
        │
   ┌────┴─────────┐    ┌──────────────────┐
   │  PostgreSQL   │    │  Bot (aiogram)   │
   │  (5432)       │    │  + cursor-agent  │
   │  внутр. порт  │    │  Telegram polling│
   └──────────────┘    └──────────────────┘
                              │
                       ┌──────┴──────┐
                       │ /var/kb/    │  ← локальная копия БЗ
                       │ (volume)    │     синхр. с NextCloud
                       └─────────────┘
```

**Потоки данных:**

| # | Поток | Описание |
|---|-------|----------|
| 1 | Пользователь → Telegram → **Бот** | Polling, без внешних портов |
| 2 | Бот → **cursor-agent** → AI → файлы БЗ | Обработка запросов, чтение/запись файлов |
| 3 | Бот → **NextCloud** (WebDAV) | Синхронизация изменений |
| 4 | Пользователь → Telegram → **Mini App** | HTTPS через Nginx (отдельный поддомен) |
| 5 | NextCloud → **Obsidian** (клиент) | Синхронизация на ваше устройство |

### Файлы конфигурации

```
/opt/knowledge-base-bot/           ← проект
├── .env                           ← переменные окружения
├── docker-compose.yml             ← базовый compose
├── docker-compose.prod.yml        ← продакшен-оверрайд
├── nginx/
│   ├── example-site.conf          ← полный пример (NextCloud + Mini App)
│   └── miniapp-location.conf      ← отдельный server-блок для Mini App
└── logs/                          ← логи бота и miniapp

/etc/nginx/sites-available/
├── nextcloud.example.ru                ← ваш существующий конфиг NextCloud
└── knowledgebotminiapp.example.ru      ← конфиг Mini App (из шага 6)

/var/lib/knowledge-base-bot/kb/    ← локальная копия БЗ (Docker volume)
```
