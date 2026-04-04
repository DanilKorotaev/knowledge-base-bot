# KB App API: `POST /api/query/voice` (iOS native client)

**Status:** Pending — iOS клиент уже шлёт multipart на этот путь (`URLSessionKnowledgeBaseAPIClient.sendVoiceRecording`); сервер нужно реализовать.

**Правила кода:** `.cursor/rules/development.md` (type hints, PEP 8, docstrings, логирование, тесты).

## Цель

Один HTTP-эндпоинт для **нативного iOS**: загрузка аудио (AAC/m4a), опциональная подсказка текста с клиента, флаг «с БЗ», привязка к **сессии**. Дальше — тот же смысловой пайплайн, что у Telegram после расшифровки: запись user-сообщения, вызов обработки запроса, ответ ассистента в треде.

## Существующий код для переиспользования

| Компонент | Файл / модуль | Заметка |
|-----------|----------------|---------|
| Расшифровка Whisper | `services/transcription_service.py` (`TranscriptionService.transcribe`) | Уже используется в `handlers/voice.py` для Telegram |
| Полировка текста (опц.) | `TranscriptionService.polish_transcription` | По желанию после Whisper |
| Обработка запроса | `services/query_processing_service.py` | Вход: текст; нужна точка входа **без** `aiogram.types.Message` или тонкая обёртка |
| Сессии / сообщения в БД | `database/postgresql_db.py`, `services/session_service.py` | Как в Mini App API |
| Mini App HTTP-паттерн | `miniapp/api/routes.py`, `miniapp/api/auth.py` | Сейчас auth через Telegram `initData`; для iOS — **отдельный** Bearer (см. ниже) |

## Контракт (согласован с iOS, 2026-04)

**Метод и путь:** `POST /api/query/voice`  
**Заголовок:** `Authorization: Bearer <token>` (тот же механизм, что для остальных KB App routes на стороне клиента: `AppConfiguration` / env).

**Content-Type:** `multipart/form-data`

| Part (name) | Обязательно | Описание |
|-------------|---------------|----------|
| `session_id` | да | Строка (iOS шлёт string id сессии, как в `GET /api/sessions`) |
| `use_knowledge_base` | да | `true` / `false` |
| `transcription_hint` | нет | Текст из UI до Whisper; может быть пустым |
| `audio` | да | Файл, у клиента имя вида `*.m4a`, `Content-Type: audio/mp4` |

**Ответ 200:** JSON, совместимый с тем, как iOS парсит ответы чата:

- Предпочтительно: `{ "messages": [ ... ] }` — массив `KBMessage`-совместимых объектов (`id`, `role`, `content`, `created_at` ISO8601), **или**
- Прямой массив `[...]`.

Если сервер возвращает только `transcription` + `response` (как в концепции «Архитектура и бэкенд API»), адаптер должен **собрать** два сообщения (user + assistant) и положить в `messages`, либо расширить iOS-декодер (лучше сервер отдаёт уже `messages`).

**Ошибки:** 401 (auth), 403 (нет доступа к сессии), 404 (сессия), 413 (файл слишком большой), 422 (валидация).

## Алгоритм на сервере (предлагаемый)

1. Проверить Bearer и сопоставить пользователя API с записью в БД (отдельная таблица / токен — как в общей спецификации KB App API).
2. Загрузить `session_id`, проверить владение сессией (аналог `_verify_session_access` в Mini App, но по **API user**, не `telegram_id`).
3. Сохранить аудио во временный файл.
4. `TranscriptionService.transcribe(path)` → текст; при необходимости объединить с `transcription_hint` (политика: подсказка только если Whisper пустой — на усмотрение).
5. Сохранить user message (роль user, контент — итоговая формулировка запроса).
6. Вызвать `QueryProcessingService` (или существующий async-путь из текстового сообщения) для генерации ответа ассистента и записи в БД.
7. Вернуть обновлённый список сообщений сессии (или последние N).

## Тесты

- Unit: разбор multipart, ошибки без `audio`.
- Интеграция (по возможности): мок `TranscriptionService`, проверка записи сообщений в тестовую БД.

## Связанные задачи

- Nextcloud: `Документация/Задачи/KB App API — бэкенд для iOS/todo.md`
- iOS: `sendVoiceRecording` в `KnowledgeBaseAPIClient.swift`, stub в `StubChatAPIClient`

## Acceptance

- [ ] Реализован route под префиксом того же FastAPI-приложения, что и остальной KB App API (или отдельный сервис с импортом `services/`).
- [ ] Поведение согласовано с iOS multipart (имена полей как в таблице).
- [ ] Логирование без секретов; ошибки не утекают в ответ как сырой traceback.
