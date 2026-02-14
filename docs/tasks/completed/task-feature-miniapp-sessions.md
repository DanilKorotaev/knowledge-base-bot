# Telegram Mini App для управления сессиями

**Статус**: ✅ Выполнено  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции
**Дата завершения**: 2026-02-14

## Описание

Реализация Telegram Mini App для удобного управления сессиями чата. Mini App позволяет пользователю просматривать список сессий, переключаться между ними, просматривать историю сообщений, управлять сессиями и просматривать файлы базы знаний в удобном веб-интерфейсе.

## Цели

1. ✅ Создать Telegram Mini App для управления сессиями
2. ✅ Реализовать список сессий с фильтрацией и поиском
3. ✅ Реализовать просмотр истории сообщений сессии в форматированном виде
4. ✅ Реализовать переключение активной сессии из Mini App
5. ✅ Реализовать удаление и управление сессиями
6. ✅ Интегрировать Mini App с ботом через Web App API

## Реализованные задачи

### Структура Mini App

- [x] Создать структуру папок для Mini App:
  ```
  miniapp/
  ├── static/
  │   ├── index.html
  │   ├── css/
  │   │   └── styles.css
  │   └── js/
  │       ├── app.js
  │       └── sessions.js
  ├── api/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── routes.py
  │   └── auth.py
  └── Dockerfile
  ```
- [x] Создать базовый HTML с Telegram Web App API
- [x] Создать стили для красивого отображения сессий и сообщений
- [x] Создать JavaScript логику для работы с сессиями

### API для Mini App

- [x] Реализовать REST API endpoints:
  - `GET /api/sessions` - получить список сессий пользователя
  - `GET /api/sessions/{session_id}` - получить детали сессии
  - `GET /api/sessions/{session_id}/messages` - получить сообщения сессии
  - `POST /api/sessions/{session_id}/switch` - переключиться на сессию
  - `POST /api/sessions/{session_id}/delete` - удалить сессию (status → deleted)
  - `POST /api/sessions/{session_id}/end` - завершить сессию (status → completed)
  - `GET /api/sessions/search?q=...` - поиск сессий по ID или содержимому
  - `GET /api/files/view?path=...` - получение содержимого файла
  - `GET /api/files/list?path=...` - получение списка файлов/папок
- [x] Реализовать аутентификацию через Telegram Web App initData
- [x] Реализовать валидацию пользователя и проверку прав доступа
- [x] Реализовать обработку ошибок и возврат понятных сообщений

### Интерфейс списка сессий

- [x] Реализовать отображение списка сессий (ID, тип, статус, сообщения, дата, индикатор)
- [x] Реализовать фильтрацию по статусу (все, активные, завершённые)
- [x] Реализовать поиск по ID или содержимому

### Просмотр сессии

- [x] Реализовать отображение истории сообщений (разделение ролей, Markdown, время)
- [x] Реализовать красивую верстку диалога (chat-style)
- [x] Реализовать прокрутку к последнему сообщению

### Управление сессиями

- [x] Реализовать кнопку "Переключиться" для активации сессии
- [x] Реализовать кнопку "Удалить" с подтверждением (модальное окно)
- [x] Реализовать кнопку "Завершить" для завершения активной сессии
- [x] Реализовать кнопку "Вернуться в чат" для закрытия Mini App

### Просмотр файлов базы знаний

- [x] Реализовать API endpoints для файлов (`GET /api/files/view`, `GET /api/files/list`)
- [x] Реализовать HTML-страницу с Markdown-рендерером (marked.js)
- [x] Реализовать навигацию по файлам/папкам с хлебными крошками
- [x] Реализовать кнопку `WebAppInfo(url=...)` в keyboards.py (`get_file_view_button`)

### Интеграция с ботом

- [x] Добавить inline-кнопку Mini App в главное меню (`get_main_menu_inline_keyboard_with_admin`)
- [x] Добавить `get_miniapp_inline_keyboard()` для отдельной кнопки Mini App
- [x] Добавить `get_file_view_button()` для просмотра файлов
- [x] Реализовать обновление активной сессии через API

### Развертывание

- [x] Создать Dockerfile для Mini App (`miniapp/Dockerfile`)
- [x] Добавить сервис miniapp в `docker-compose.yml`
- [x] Настроить переменные окружения (`MINIAPP_URL`, `MINIAPP_PORT`, `MINIAPP_HOST`)
- [x] Настроить CORS для API
- [x] Настроить HTTPS для Web App (скрипт `scripts/dev_miniapp.sh` с cloudflared для разработки)

### Уведомления в чат

- [x] Реализовать модуль `miniapp/api/notify.py` для отправки сообщений через Telegram Bot API
- [x] Уведомления при переключении сессии (🔄)
- [x] Уведомления при завершении сессии (⏹)
- [x] Уведомления при удалении сессии (🗑)

### Отображение вложений

- [x] Прокси-эндпоинт `GET /api/attachments/{id}/file` для скачивания файлов через Telegram API
- [x] Отображение фото (lazy-load через blob URL)
- [x] Воспроизведение голосовых сообщений (audio player)
- [x] Отображение документов, аудио, видео с иконками и размером

### Редизайн экрана сессии

- [x] Компактный хедер: `← #ID ℹ️ ⋮`
- [x] Модальное окно информации о сессии (кнопка ℹ️)
- [x] Bottom sheet для действий (кнопка ⋮)
- [x] Сообщения занимают весь экран (flex layout, без двойного скролла)

### Автоматизация локальной разработки

- [x] Скрипт `scripts/dev_miniapp.sh` для запуска с cloudflared tunnel
- [x] Автоматическое создание туннеля и подстановка MINIAPP_URL в `.env`
- [x] Запуск docker-compose и корректная остановка при выходе

## Технические детали

### Актуальные детали кодовой базы

- **Статусы сессий** (`utils/constants.py`): `active`, `completed`, `deleted` (enum `SessionStatus`)
- **Типы сессий** (`utils/constants.py`): `query_with_kb`, `empty_chat` (enum `SessionType`)
- **Роли сообщений** (`utils/constants.py`): `user`, `assistant` (enum `MessageRole`)
- **Метод получения пользователя**: `db.ensure_user(telegram_id, username)` — создает пользователя если не существует
- **Удаление сессии**: `db.update_session(session_id, status="deleted")` — не отдельный метод, а обновление статуса
- **Получение БД**: `from utils.db_helpers import get_db` → `db = await get_db()`
- **FastAPI**: уже в `requirements.txt`
- **Бот (bot instance)**: создается локально в `bot.py:main()`, не экспортируется на уровне модуля
- **Кнопка "Мои сессии"**: обрабатывается через `callback_data="main_sessions"` (inline-кнопка)

### Архитектура

```
Telegram → Bot (aiogram) → обработчики
                  ↓
            Mini App (FastAPI) ← Telegram WebApp JS API
                  ↓
            database (SQLite/PostgreSQL)
                  ↓
            базы знаний (файлы на диске)
```

### Ключевые файлы

- `miniapp/api/main.py` — FastAPI приложение (CORS, статика, lifecycle)
- `miniapp/api/routes.py` — API маршруты (сессии, файлы, вложения, поиск)
- `miniapp/api/auth.py` — Аутентификация через Telegram initData (HMAC-SHA256)
- `miniapp/api/notify.py` — Отправка уведомлений в чат через Telegram Bot API
- `miniapp/static/index.html` — HTML с Telegram Web App API, модалки, bottom sheet
- `miniapp/static/css/styles.css` — Стили (Telegram theme vars, skeleton, chat-style, bottom sheet)
- `miniapp/static/js/sessions.js` — API клиент (SessionsManager)
- `miniapp/static/js/app.js` — Главная логика (навигация, рендеринг, вложения, действия)
- `miniapp/Dockerfile` — Docker-образ
- `config.py` — `MINIAPP_URL`, `MINIAPP_PORT`, `MINIAPP_HOST`
- `handlers/keyboards.py` — `get_miniapp_inline_keyboard()`, `get_file_view_button()`, кнопка в главном меню
- `scripts/dev_miniapp.sh` — Скрипт локальной разработки с cloudflared

### Настройка

1. Установить переменные окружения:
   ```
   MINIAPP_URL=https://your-domain.com     # Публичный HTTPS URL Mini App
   MINIAPP_PORT=8080                        # Порт Mini App
   MINIAPP_HOST=0.0.0.0                     # Хост Mini App
   ```

2. HTTPS обязателен (Telegram требует для Web Apps). Варианты:
   - nginx reverse proxy + Let's Encrypt
   - ngrok (для разработки)
   - Cloudflare Tunnel

3. Запуск: `docker-compose up -d miniapp`

## Примечания

- **HTTPS обязателен** для Web Apps — Telegram требует HTTPS
- Для локальной разработки используется `cloudflared` tunnel (автоматизирован в `scripts/dev_miniapp.sh`)
- API защищен проверкой Telegram initData (HMAC-SHA256 с bot token)
- При переключении сессии из Mini App, Mini App закрывается и пользователь возвращается в чат
- Уведомления в чат отправляются напрямую через Telegram Bot API (`miniapp/api/notify.py`), минуя aiogram
- Вложения отображаются через прокси-эндпоинт для безопасного доступа к файлам Telegram
- Файловый браузер ограничен `LOCAL_KB_PATH` с защитой от path traversal
- Экран сессии использует компактный хедер с ℹ️ (инфо) и ⋮ (действия) для максимизации области сообщений
