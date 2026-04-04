# Health Sync API

Минимальный FastAPI-сервис для webhook **HealthSync** (iOS): после загрузки JSON в Nextcloud связывает `HealthData/workouts/*.json` с заметками `Тренировки/ГГГГ/<Месяц>/`. Логика линковки вынесена в пакет [`packages/health_linking`](../packages/health_linking/README.md).

**Сборка Docker** выполняется из **корня репозитория** `knowledge-base-bot` (`context: .`, `dockerfile: health-sync-api/Dockerfile`).

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

Нужен `PYTHONPATH` на каталог, где лежит пакет `health_linking` (`packages/health_linking`):

```bash
cd knowledge-base-bot/health-sync-api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=../packages/health_linking
export HEALTH_SYNC_API_TOKEN=test
export HEALTH_SYNC_KB_PATH=/path/to/kb
uvicorn app.main:app --reload --port 8090
```

### Тесты

```bash
cd knowledge-base-bot
PYTHONPATH=packages/health_linking health-sync-api/.venv/bin/python -m unittest discover -s health-sync-api/tests -p 'test*.py' -v
```
