# KB App API (MVP) — пакет `kb_app_api/`

**Статус:** функционально готово; секреты и прод-URL задаются при деплое (см. `kb-app-api/env.example`).

**Чеклист деплоя и E2E:** Nextcloud `Документация/Задачи/KB App API — бэкенд для iOS/Чеклист — деплой и интеграция.md`.

## Сделано

- Маршруты по контракту iOS; Docker (`kb-app-api/Dockerfile`, `docker-compose` + prod override).
- Опциональный **`POST /api/auth/token`**: `KB_APP_API_TOKEN_ENDPOINT_ENABLED`, `KB_APP_API_TOKEN_ISSUE_SECRET`, выдача `KB_APP_API_TOKEN`.

## Деплой

- Переменные из `.env` / CI — без хранения значений в репозитории.

Контракт: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.
