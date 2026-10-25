# KB App API — Docker

Сборка из **корня** репозитория `knowledge-base-bot`:

```bash
docker compose build kb-app-api
docker compose up -d kb-app-api
```

Переменные окружения — см. `env.example` и корневой `.env` (секреты задаются при деплое, не в репозитории).

Порт по умолчанию: `8091` (`KB_APP_API_PORT`).

- `GET /health` — liveness
- `GET /metrics` — Prometheus (без auth; scrape с Mac mini)

### Auth + Nextcloud App Password

При `register` API создаёт NC-пользователя (OCS) и в фоне минтит **App Password** (`getapppassword`), шифрует Fernet (`KB_NC_TOKEN_KEY` или derive от JWT secret) в `users.nc_app_password_enc`.  
`change-password` синхронизирует пароль в NC и перевыпускает App Password.  
`kb_folder` (по умолчанию `/`) — корень KB внутри NC home; `PATCH /api/auth/me`.  
Список/создание папок для Settings: `GET|POST /api/auth/nc-folders` (через App Password, в NC home).  
В публичном API только `has_nc_app_password` + `kb_folder` (сам токен не отдаём).

KB App sync/links (`health`, revert, query file changes, open/share-link) идут через **App Password пользователя** (`SyncService.for_user` / `NextCloudService.for_user`), не через bot share. Telegram-бот по-прежнему использует `NEXTCLOUD_BOT_*` для общей KB.

Продакшен: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` — сервис `kb-app-api` слушает `127.0.0.1:8091`; снаружи — nginx + HTTPS (конфиг **только на сервере**, не в git). См. заметку Nextcloud «Продакшен-сервер — SSH и статус бота».
