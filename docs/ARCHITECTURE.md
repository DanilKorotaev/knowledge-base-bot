# Архитектура — Knowledge Base App backend

Актуальная схема продукта. Legacy Telegram Bot / Mini App: [telegram/](telegram/README.md)  
(revival: [task-epic-telegram-multiuser.md](tasks/pending/task-epic-telegram-multiuser.md)).

## Общая картина

```
┌──────────────────┐     ┌───────────────────┐
│  iOS KB App      │     │  (later) Web /    │
│  JWT + offline │     │  Mini App / TG    │
└────────┬─────────┘     └─────────┬─────────┘
         │  HTTPS Bearer           │
         ▼                         ▼
┌────────────────────────────────────────────┐
│              kb_app_api (FastAPI)           │
│  auth · sessions · messages · voice · jobs │
│  boards · structured UI · push · files     │
└───────┬──────────────┬───────────┬─────────┘
        │              │           │
        ▼              ▼           ▼
┌──────────────┐ ┌──────────┐ ┌────────────┐
│  PostgreSQL  │ │ Cursor   │ │ Nextcloud  │
│  (users,     │ │ CLI      │ │ WebDAV     │
│   sessions,  │ │ (agent)  │ │ per-user   │
│   boards…)   │ │          │ │ App Pass   │
└──────────────┘ └────┬─────┘ └─────▲──────┘
                      │             │
                      ▼             │
               ┌──────────────┐     │
               │ Local vault  │─────┘ sync
               │ users/<login>│
               └──────────────┘
```

Отдельно: **health-sync-api** (webhook Apple Health → линковка заметок) — [../health-sync-api/README.md](../health-sync-api/README.md).

## Идентичность и доступ

| Было (deprecated) | Сейчас |
|-------------------|--------|
| Shared Bearer / `KB_APP_API_TELEGRAM_ID` | JWT access + refresh, `users.login` |
| Whitelist `telegram_id` как primary | App user; `telegram_id` nullable (link later) |
| Один `LOCAL_KB_PATH` на всех | `LOCAL_KB_PATH/users/<login>/` (`vault_root_relative`) |
| Bot Nextcloud share (`NEXTCLOUD_BOT_*`) | Per-user App Password + `kb_folder` |

Контракт HTTP/JSON для клиента: iOS `docs/KB_APP_API_CONTRACT.md` (репозиторий knowledge-base-app-ios).

## Vault и Cursor isolation

- **Vault root** — `kb_app_api/vault_paths.py`: `users/<login>/` под `LOCAL_KB_PATH`.
- **`cursor_isolation`**
  - `strict` — soft-jail: агент видит только vault пользователя
  - `host` — cwd = vault, без soft-jail (операторский режим)
- Env scrub для `cursor-agent`: не светить host secrets процессу агента.
- Относительный путь vault для бота/legacy: `KB_BOT_VAULT_RELATIVE` / cutover docs (ops).

## Runtime: где крутится API

| Среда | Как |
|-------|-----|
| **Prod (Mac mini)** | LaunchAgent `com.coredan.kb-app-api-host` (uvicorn). Push на `main`/`develop` → CI → redeploy; **не** `kickstart -k` mid-agent (см. `.cursor/rules`). |
| **Staging** | Docker Compose (`kb-staging-kb-app-api` и др.) |
| **Local** | `uvicorn kb_app_api.main:app` или `docker compose up kb-app-api` |

Безопасный рестарт host: `scripts/safe-restart-kb-app-api-host.sh`.

## Компоненты `kb_app_api`

| Область | Модули (уровень пакета) | Назначение |
|---------|-------------------------|------------|
| Entry | `main.py`, `deps.py`, `errors.py` | App, JWT user, ошибки |
| Auth | `auth_service`, `jwt_tokens`, `passwords`, `routes/auth.py`, `routes/me.py` | Register/login/refresh, `/me`, NC folders |
| NC provision | `nextcloud_provision`, `nc_token_crypto`, `kb_folder` | NC user + App Password |
| Chat | `routes/sessions`, `messages`, `attachments`, `voice`, `share` | Сессии, compose, голос, шаринг |
| Jobs | `query_jobs/` | Фоновый Cursor, SSE |
| Boards | `boards/`, `boards_catalog`, `routes/boards` | Overview/Actions, presets |
| UI | `structured_ui/`, `routes/ui_events`, `remote_ui` | Remote structured screens |
| Push | `routes/devices`, `apns_push_service`, `push_dispatch` | APNs |
| Metrics | `metrics.py`, `routes/health` | `/health`, Prometheus |
| Admin | `routes/admin_users` | Admin users (по мере готовности) |

Общие слои репо, которыми пользуется и API, и legacy bot: `database/`, `services/` (Cursor, sync, sessions), `config.py`, `agent/` (system + channel prompts).

## Поток: сообщение из iOS

1. Клиент: `Authorization: Bearer <access>`; при 401 — refresh.
2. `POST …/messages` или compose / voice → создаётся / продолжается session.
3. Тяжёлый Cursor уходит в **query job** (не блокирует HTTP worker).
4. Ответ: SSE и/или push; изменения файлов в vault пользователя; sync в NC через App Password.
5. Boards / Structured UI читают тот же vault + метаданные в Postgres (`kb_app_boards` с PK `(user_id, id)`).

## Boards

- По умолчанию у нового пользователя Overview/Actions **пустые**.
- Пресеты (`active-jobs`, `actions-presets`, …): `GET/POST/DELETE /api/boards/presets…`.
- Каталог и install: `kb_app_api/boards/presets.py`.

## Legacy Telegram (кратко)

Код: `bot.py`, `handlers/`, `miniapp/`.  
Доки: [telegram/](telegram/README.md).  
Не описывать здесь whitelist/handlers детально — см. [telegram/ARCHITECTURE_BOT.md](telegram/ARCHITECTURE_BOT.md).

## Связанные доки

- [../README.md](../README.md) — лицо репо
- [../kb-app-api/README.md](../kb-app-api/README.md) — Docker API
- [OPS.md](OPS.md) — актуальный деплой; stubs/archive bot-era
- [kb-app-api/](kb-app-api/README.md) — feature guides
- [todo.md](todo.md) — задачи
