# Health Sync API

Минимальный FastAPI-сервис для webhook **HealthSync** (iOS): после загрузки JSON в Nextcloud связывает `HealthData/workouts/*.json` с заметками `Тренировки/ГГГГ/<Месяц>/`.

## Endpoint

- `POST /api/health/sync-complete` — тело как в iOS: `{"date":"yyyy-MM-dd","files":["HealthData/..."]}`
- Заголовок: `Authorization: Bearer <HEALTH_SYNC_API_TOKEN>`
- `GET /health` — для Docker healthcheck

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `HEALTH_SYNC_API_TOKEN` | Обязательный секрет (тот же токен в настройках клиента, когда будет поддержка в приложении) |
| `HEALTH_SYNC_KB_PATH` | Корень базы знаний (в контейнере: `/var/knowledge-base-bot/kb`) |
| `LOG_LEVEL` | По умолчанию `INFO` |

## iOS

Сейчас `SyncWebhookClient` в HealthSync может слать только JSON без `Authorization`. Для продакшена добавьте передачу Bearer-токена (UserDefaults / Keychain) и заголовок в запросе — либо временно проксируйте через доверенную сеть.

## Локальный запуск

```bash
cd health-sync-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export HEALTH_SYNC_API_TOKEN=test
export HEALTH_SYNC_KB_PATH=/path/to/kb
uvicorn app.main:app --reload --port 8090
```
