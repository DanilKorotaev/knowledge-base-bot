# KB App API (MVP) — пакет `kb_app_api/`

**Статус:** MVP задеплоен в коде; дальше — пайплайн запросов как у бота, Whisper, вложения, revert.

## Сделано

- FastAPI: `GET /health`, `GET/POST /api/sessions`, `GET/POST /api/sessions/{id}/messages` (+ SSE), `POST /api/query/voice` (заглушка), `GET /api/files/changes`, 501 на attachments и `files/revert`.
- Bearer: `KB_APP_API_TOKEN`, пользователь: `KB_APP_API_TELEGRAM_ID`.
- БД: `sessions.display_title`, обновление `sessions.updated_at` при новом сообщении.

## Следующие шаги

1. Подключить реальную обработку текста (headless или адаптация `QueryProcessingService` без Telegram `Message`).
2. `POST /api/query/voice`: `TranscriptionService` + тот же пайплайн, что текст — см. `task-api-kb-app-voice-query-ios.md`.
3. Docker / compose, при необходимости `POST /api/auth/token`.

Контракт для iOS: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.
