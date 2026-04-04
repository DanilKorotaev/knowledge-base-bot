# Health Sync API

Минимальный FastAPI-сервис для webhook **HealthSync** (iOS): после загрузки JSON в Nextcloud связывает `HealthData/workouts/*.json` с заметками `Тренировки/ГГГГ/<Месяц>/`. Логика линковки вынесена в пакет [`packages/health_linking`](../packages/health_linking/README.md).

**Сборка Docker** выполняется из **корня репозитория** `knowledge-base-bot` (`context: .`, `dockerfile: health-sync-api/Dockerfile`).

**Path 1 vs Path 2:** Path 1 — этот сервис после загрузки JSON с iOS. Path 2 — бот при сохранении заметки `Тренировки/` (`health_linking_hook` в основном приложении), без дополнительного HTTP.

## Endpoints

| Метод | Путь | Авторизация |
|-------|------|-------------|
| `GET` | `/health` | Нет (healthcheck) |
| `POST` | `/api/health/sync-complete` | `Authorization: Bearer <HEALTH_SYNC_API_TOKEN>` |

Тело `sync-complete` совпадает с `SyncWebhookPayload` в iOS HealthSync:

```json
{"date":"yyyy-MM-dd","files":["HealthData/daily/....json","HealthData/workouts/....json"]}
```

### Коды ответов

| Код | Когда |
|-----|--------|
| `200` | Синк обработан; в теле поля `linked`, `skipped`, `errors` |
| `401` | Нет заголовка Bearer или неверная схема |
| `403` | Неверный токен |
| `422` | Невалидное JSON-тело (Pydantic) |
| `503` | `HEALTH_SYNC_API_TOKEN` не задан на сервере |

### Пример `curl`

```bash
curl -sS -X POST "http://127.0.0.1:8090/api/health/sync-complete" \
  -H "Authorization: Bearer $HEALTH_SYNC_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"date":"2026-04-05","files":["HealthData/workouts/2026-04-05_workout.json"]}'
```

### Nginx (прод)

Прокси на тот же хост, где слушает uvicorn (порт по умолчанию `8090`):

```nginx
location /api/health/ {
    proxy_pass http://127.0.0.1:8090/api/health/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
location = /health {
    proxy_pass http://127.0.0.1:8090/health;
}
```

`GET /health` можно оставить только для Docker/внутренней сети; наружу достаточно `POST /api/health/sync-complete` с Bearer.

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `HEALTH_SYNC_API_TOKEN` | Обязательный секрет (тот же токен в настройках клиента, когда будет поддержка в приложении) |
| `HEALTH_SYNC_KB_PATH` | Корень базы знаний (в контейнере: `/var/knowledge-base-bot/kb`) |
| `LOG_LEVEL` | По умолчанию `INFO` |

## iOS (HealthSync)

Клиент отправляет тот же JSON и заголовок `Authorization: Bearer …`, если в настройках задан токен (см. переменные окружения / поля конфигурации приложения). Без токена webhook можно не вызывать или вызывать только после настройки сервера.

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
