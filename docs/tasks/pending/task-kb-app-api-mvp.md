# KB App API (MVP) — пакет `kb_app_api/`

**Статус:** основные маршруты готовы; инфраструктура (Docker, опциональный `/api/auth/token`) — отдельно.

## Сделано

- FastAPI: сессии, сообщения (+ SSE), голос, `GET /api/files/changes`, **`POST /api/files/revert`**, **`POST .../attachments`** (файл на диск → `process_query_for_api` + запись в `attachments`).
- `QueryProcessingService.process_query_for_api`, откат: `kb_app_api/revert_helpers.py` (как в Telegram `revert_change_callback`).
- Bearer, БД — как ранее.

## Опционально позже

- Docker / compose для процесса `kb_app_api`.
- `POST /api/auth/token`.

Контракт: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.
