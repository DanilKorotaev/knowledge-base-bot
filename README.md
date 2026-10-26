# Knowledge Base App — backend

Бэкенд **Knowledge Base App**: multi-user JWT API, per-user vault в Nextcloud, Cursor CLI, boards / Structured UI, push. Клиент — [iOS app](https://github.com/DanilKorotaev/knowledge-base-app-ios).

Имя репозитория `knowledge-base-bot` — историческое. **Основной продукт сейчас — `kb_app_api`**, не Telegram-бот.

## Что есть

- **KB App API** (`kb_app_api/`) — FastAPI: auth (login/register/refresh), sessions, compose, voice, query jobs, boards + presets, Structured UI, devices/push
- **Per-user vault** — `users/<login>/`, Cursor isolation (`strict` / `host`), Nextcloud App Password на пользователя
- **Health Sync API** — отдельный сервис для Apple Health → заметки ([health-sync-api/README.md](health-sync-api/README.md))
- **Telegram bot + Mini App** — **deprecated** (legacy код ещё в репо; revival — один эпик ниже)

Контракт для iOS: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`. Docker API: [kb-app-api/README.md](kb-app-api/README.md).

## Telegram (deprecated)

Пользовательский Telegram-бот и Mini App **не являются основным каналом**. Пока multi-user identity строится вокруг App login; бот исторически завязан на `telegram_id`.

План вернуть Telegram как вторичный канал (1:1 link, invite, bot по `user_id`):  
→ **[docs/tasks/pending/task-epic-telegram-multiuser.md](docs/tasks/pending/task-epic-telegram-multiuser.md)**

CI/build **уведомления** в Telegram — отдельно: alerts only, это не user-facing бот.

Документация по старому боту/Mini App пока в корне `docs/` (MINIAPP, SETUP_*); перенос в `docs/telegram/` — [задача](docs/tasks/pending/task-doc-relocate-telegram-legacy.md).

## Быстрый старт (API)

### Требования

- Python 3.11+
- PostgreSQL (или SQLite для локальных тестов)
- Cursor CLI (для query pipeline)
- Nextcloud (per-user App Passwords в проде)

### Локально

```bash
git clone https://github.com/DanilKorotaev/knowledge-base-bot.git
cd knowledge-base-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # или env.example — смотрите актуальный шаблон в репо
```

Запуск API (пример через compose):

```bash
docker compose build kb-app-api
docker compose up -d kb-app-api
# GET http://127.0.0.1:8091/health
```

Подробнее: [kb-app-api/README.md](kb-app-api/README.md), [docs/QUICK_START_DOCKER.md](docs/QUICK_START_DOCKER.md).  
Deploy / host vs staging: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), [docs/GITHUB_ACTIONS_DEPLOY.md](docs/GITHUB_ACTIONS_DEPLOY.md) (аудит — [задача](docs/tasks/pending/task-doc-deploy-and-releases-audit.md)).

## Документация

Индекс: [docs/README.md](docs/README.md)

| | |
|--|--|
| Архитектура | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — refresh: [задача](docs/tasks/pending/task-doc-architecture-kb-app.md) |
| Задачи | [docs/todo.md](docs/todo.md) |
| Эпик доков | [task-epic-documentation-refresh.md](docs/tasks/pending/task-epic-documentation-refresh.md) |
| Эпик web-клиентов | [task-epic-web-kb-clients.md](docs/tasks/pending/task-epic-web-kb-clients.md) |

## Структура (кратко)

```
knowledge-base-bot/
├── kb_app_api/           # KB App API (основной runtime)
├── kb-app-api/           # Docker/README для API
├── health-sync-api/      # Health webhook
├── database/ services/   # Общие слои (в т.ч. legacy bot)
├── handlers/ bot.py      # Legacy Telegram (deprecated)
├── miniapp/              # Legacy Mini App (deprecated)
├── agent/                # System / channel prompts для Cursor
├── docs/                 # Документация и tasks
└── .cursor/rules/        # Правила агентов (в т.ч. docs-keep-current)
```

## Лицензия

MIT License

## Автор

DanilKorotaev

## Ссылки

- [GitHub — backend](https://github.com/DanilKorotaev/knowledge-base-bot)
- [GitHub — iOS](https://github.com/DanilKorotaev/knowledge-base-app-ios)
