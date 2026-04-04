# Контракт и эксплуатация Health Sync API (FastAPI)

**Статус:** Запланировано  
**Приоритет:** Низкий–средний  
**Категория:** Документация / ops

## Текущее состояние (репозиторий)

- **Сервис:** `health-sync-api/` — FastAPI, uvicorn `:8090`.
- **Эндпоинты:**
  - `GET /health` — без авторизации, для Docker healthcheck и мониторинга.
  - `POST /api/health/sync-complete` — тело JSON `{ "date": "yyyy-MM-dd", "files": [ "HealthData/..." ] }`, заголовок `Authorization: Bearer <HEALTH_SYNC_API_TOKEN>`.
- **Клиент iOS:** `HealthSync` — `SyncWebhookPayload`, опционально `HEALTHSYNC_SYNC_WEBHOOK_TOKEN` / `SYNC_WEBHOOK_TOKEN` в настройках.

## Что зафиксировать в коде/доках

- [ ] **README** `health-sync-api/README.md`: таблица кодов ответов (200, 401, 403, 503, 422), пример `curl` с Bearer.
- [ ] **Nginx** (прод): пример `location` proxy для `https://…/api/health/` → `127.0.0.1:8090` (как у miniapp в `docker-compose.prod.yml`).
- [ ] **Логи:** при необходимости — `request_id` в заголовке и structured JSON-логи (см. `task-tech-structured-logging.md` в общем todo).
- [ ] **Версионирование API:** при ломающих изменениях — префикс `/api/v2/health/...` или поле `version` в теле (пока не требуется).

## Связанные задачи

- Path 2 в боте: `task-feature-bot-health-link-on-note-saved.md`
- Общий модуль линковки: `task-tech-health-linking-shared-python-module.md`

## Критерии готовности

- Новый разработчик может поднять сервис и проверить контракт без чтения исходников FastAPI.
