# KB App API (MVP) — пакет `kb_app_api/`

**Статус:** текст и голос идут через **тот же пайплайн**, что у бота (`process_query_for_api`); дальше — вложения, revert, Docker.

## Сделано

- FastAPI: `GET /health`, `GET/POST /api/sessions`, `GET/POST /api/sessions/{id}/messages` (+ SSE с чанками Cursor), `POST /api/query/voice` (Whisper + полировка + пайплайн), `GET /api/files/changes`, 501 на attachments и `files/revert`.
- `QueryProcessingService.process_query_for_api` — без Telegram UI; `handle_file_changes` вынесен в `_apply_file_changes_storage` + `handle_file_changes_for_api`.
- Bearer: `KB_APP_API_TOKEN`, пользователь: `KB_APP_API_TELEGRAM_ID`.
- БД: `sessions.display_title`, обновление `sessions.updated_at` при новом сообщении.

## Следующие шаги

1. `POST .../attachments` и реальный `POST /api/files/revert` (по логике бота / откат из `file_changes`).
2. Docker / compose для `kb_app_api`, при необходимости `POST /api/auth/token`.

Контракт для iOS: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.
