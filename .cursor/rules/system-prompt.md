# Системный промпт для репозитория knowledge-base-bot

Этот проект — бэкенд персональной базы знаний: **Telegram-бот** и **KB App API** (для iOS-приложения). Агент пользователя запускается через Cursor CLI по vault.

## О проекте

- **Название**: Knowledge Base Bot (+ KB App API)
- **Назначение**: приём запросов из Telegram и из iOS-приложения, сессии, медиа/голос, синк Nextcloud, вызов Cursor CLI по локальной копии vault
- **Технологии**: Python, aiogram, FastAPI (KB App API), Cursor CLI, PostgreSQL/SQLite, Nextcloud

## Архитектура (упрощённо)

1. Клиент (Telegram или iOS) отправляет сообщение в сессию
2. Сервис обрабатывает запрос, при необходимости синкает vault с Nextcloud
3. Cursor CLI (`cursor-agent`) работает в директории vault:
   - `agent/system_prompt.md` — общее OSS-окружение агента
   - `agent/channel_telegram_prompt.md` / `agent/channel_app_prompt.md` — возможности канала (подмешиваются по каналу)
   - vault domain prompt — только из `KB_SYSTEM_PROMPT_PATH` / опционального файла в vault оператора (не хардкодить личное в репозитории)
4. Ответ и изменения файлов возвращаются клиенту; для API — стриминг, push, Structured UI и т.д. по возможностям канала


## Структура

- `bot.py` — точка входа Telegram
- `kb_app_api/` — HTTP API для приложения
- `config.py` — конфигурация
- `database/` — PostgreSQL/SQLite
- `services/` — Cursor CLI, sync, обработка запросов
- `handlers/` — Telegram
- `agent/` — runtime-промпты агента (`system_prompt.md`, Structured UI и др.)
- `utils/` — утилиты

## Принципы разработки

1. Универсальность относительно конкретной БЗ
2. Открытость: публичный репозиторий и `docs/`
3. Локальная разработка: SQLite и локальный путь к vault
4. Канал-специфичные фичи (например Structured UI) — только в API/приложении, не ломать Telegram-путь

## Документация

Полная документация — в `docs/`. Задачи — в `docs/tasks/`.
