# KB App API — Docker

Сборка из **корня** репозитория `knowledge-base-bot`:

```bash
docker compose build kb-app-api
docker compose up -d kb-app-api
```

Переменные окружения — см. `env.example` и корневой `.env` (секреты задаются при деплое, не в репозитории).

Порт по умолчанию: `8091` (`KB_APP_API_PORT`).

Продакшен: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` — сервис `kb-app-api` слушает только `127.0.0.1` (прокси снаружи по желанию).
