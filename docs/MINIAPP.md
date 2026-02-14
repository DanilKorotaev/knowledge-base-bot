# Telegram Mini App

## Дата создания
2026-02-14

## Обзор

Telegram Mini App — веб-приложение внутри Telegram для управления сессиями чата. Предоставляет удобный интерфейс для просмотра, переключения, завершения и удаления сессий, просмотра истории сообщений с вложениями, а также навигации по файлам базы знаний.

### Возможности

- 📋 **Список сессий** — с фильтрацией по статусу и поиском
- 💬 **Просмотр сообщений** — chat-style с Markdown-рендерингом
- 📎 **Вложения** — фото, голосовые сообщения, документы
- 🔄 **Управление сессиями** — переключение, завершение, удаление
- 📁 **Файловый браузер** — навигация по базе знаний с просмотром файлов
- 🔔 **Уведомления** — отправка сообщений в чат при действиях из Mini App

---

## Архитектура

```
Telegram Client
     │
     ├──→ Bot (aiogram) ──→ PostgreSQL
     │         ↑
     └──→ Mini App (FastAPI)
              │
              ├──→ PostgreSQL (сессии, сообщения, вложения)
              ├──→ Telegram Bot API (уведомления, файлы вложений)
              └──→ Файлы базы знаний (LOCAL_KB_PATH)
```

### Компоненты

| Компонент | Технология | Описание |
|-----------|-----------|----------|
| Backend API | FastAPI + Uvicorn | REST API для сессий, файлов, вложений |
| Frontend | HTML + CSS + Vanilla JS | SPA с Telegram Web App API |
| Аутентификация | HMAC-SHA256 | Проверка `initData` от Telegram |
| Уведомления | httpx + Telegram Bot API | Прямые сообщения в чат |
| Контейнер | Docker | Отдельный сервис в docker-compose |

---

## Структура файлов

```
miniapp/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPI приложение (CORS, статика, lifecycle)
│   ├── routes.py         # API маршруты (сессии, файлы, вложения)
│   ├── auth.py           # Аутентификация через Telegram initData
│   └── notify.py         # Уведомления в чат через Telegram Bot API
├── static/
│   ├── index.html        # HTML (экраны, модалки, bottom sheet)
│   ├── css/
│   │   └── styles.css    # Стили (Telegram theme vars, адаптивные)
│   └── js/
│       ├── sessions.js   # API клиент (SessionsManager)
│       └── app.js        # Логика приложения (навигация, рендеринг)
└── Dockerfile            # Docker-образ
```

---

## API Endpoints

### Сессии

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/sessions` | Список сессий пользователя (фильтр по статусу) |
| `GET` | `/api/sessions/search?q=...` | Поиск сессий по ID или содержимому |
| `GET` | `/api/sessions/{id}` | Детали сессии |
| `GET` | `/api/sessions/{id}/messages` | Сообщения сессии с вложениями |
| `POST` | `/api/sessions/{id}/switch` | Переключиться на сессию |
| `POST` | `/api/sessions/{id}/end` | Завершить сессию |
| `POST` | `/api/sessions/{id}/delete` | Удалить сессию |

### Файлы

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/files/view?path=...` | Содержимое файла |
| `GET` | `/api/files/list?path=...` | Список файлов/папок |

### Вложения

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/attachments/{id}/file` | Прокси для скачивания файла через Telegram API |

### Аутентификация

Все запросы к API должны содержать заголовок:

```
X-Telegram-Init-Data: <initData из Telegram WebApp>
```

Валидация: HMAC-SHA256 с использованием `TELEGRAM_TOKEN` в качестве ключа.

---

## Интерфейс

### Экраны

1. **Список сессий** — карточки с ID, типом, статусом, датой; поиск и фильтры
2. **Просмотр сессии** — полноэкранный чат с компактным хедером:
   - `←` — назад к списку
   - `ℹ️` — модальное окно с информацией (статус, тип, кол-во сообщений, дата)
   - `⋮` — bottom sheet с действиями (переключить, завершить, удалить, вернуться в чат)
3. **Файловый браузер** — навигация по папкам с хлебными крошками
4. **Просмотр файла** — Markdown-рендеринг содержимого

### Уведомления в чат

При действиях из Mini App бот отправляет сообщение в чат:

- 🔄 **Переключение сессии** — информация о новой активной сессии
- ⏹ **Завершение сессии** — уведомление о завершении
- 🗑 **Удаление сессии** — уведомление об удалении

---

## Настройка

### Переменные окружения

| Переменная | Обязательна | По умолчанию | Описание |
|------------|-------------|--------------|----------|
| `MINIAPP_URL` | Да | — | Публичный HTTPS URL Mini App |
| `MINIAPP_PORT` | Нет | `8080` | Порт сервера Mini App |
| `MINIAPP_HOST` | Нет | `0.0.0.0` | Хост сервера Mini App |
| `TELEGRAM_TOKEN` | Да | — | Токен бота (используется для auth и уведомлений) |

### Docker Compose

Mini App запускается как отдельный сервис:

```yaml
miniapp:
  build:
    context: .
    dockerfile: miniapp/Dockerfile
  container_name: knowledge-base-bot-miniapp
  restart: unless-stopped
  env_file:
    - .env
  ports:
    - "${MINIAPP_PORT:-8080}:8080"
  volumes:
    - ~/.local/share/knowledge-base-bot/kb:/var/knowledge-base-bot/kb:ro
    - ./logs:/app/logs
  depends_on:
    - postgres
  networks:
    - bot-network
```

### Запуск

```bash
# Запуск только Mini App
docker-compose up -d miniapp

# Запуск всего стека
docker-compose up -d
```

---

## Локальная разработка

Для локальной разработки доступен скрипт `scripts/dev_miniapp.sh`, который автоматизирует:

1. Запуск `cloudflared` tunnel для получения HTTPS URL
2. Автоматическую подстановку URL в `.env` (`MINIAPP_URL`)
3. Запуск `docker-compose up`
4. Корректную остановку всех процессов при выходе

### Использование

```bash
# Запуск (требуется установленный cloudflared)
./scripts/dev_miniapp.sh

# Скрипт автоматически:
# 1. Запускает cloudflared tunnel → получает HTTPS URL
# 2. Обновляет MINIAPP_URL в .env
# 3. Запускает docker-compose up
# 4. При Ctrl+C корректно останавливает всё
```

### Требования

- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/) — установить через `brew install cloudflare/cloudflare/cloudflared`
- Docker и Docker Compose

---

## Безопасность

- **Аутентификация** — каждый запрос проверяется через Telegram initData (HMAC-SHA256)
- **Авторизация** — пользователь может видеть только свои сессии
- **Файловый доступ** — ограничен `LOCAL_KB_PATH` с защитой от path traversal
- **Вложения** — доступ через прокси с проверкой принадлежности сессии пользователю
- **CORS** — настроен для ограничения доступа

---

## Связанная документация

- [ARCHITECTURE.md](ARCHITECTURE.md) — Общая архитектура проекта
- [Задача: Mini App](tasks/completed/task-feature-miniapp-sessions.md) — Полная задача с чеклистом
- [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md) — Быстрый старт с Docker

---

**Документ создан:** 2026-02-14  
**Версия:** 1.0

