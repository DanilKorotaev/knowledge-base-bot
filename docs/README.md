# Документация

Продукт репозитория — **Knowledge Base App backend** (`kb_app_api`).  
Telegram-бот и Mini App — **deprecated**; revival: [tasks/pending/task-epic-telegram-multiuser.md](tasks/pending/task-epic-telegram-multiuser.md).

Обновление док-базы: [tasks/pending/task-epic-documentation-refresh.md](tasks/pending/task-epic-documentation-refresh.md).

## KB App (актуально)

- [ARCHITECTURE.md](ARCHITECTURE.md) — multi-user API, vault, isolation, runtime
- [OPS.md](OPS.md) — prod/staging deploy map (актуально)
- [kb-app-api/README.md](kb-app-api/README.md) — feature guides index (+ [auth.md](kb-app-api/auth.md))
- [../kb-app-api/README.md](../kb-app-api/README.md) — Docker / health / auth notes
- [DEVELOPMENT.md](DEVELOPMENT.md) — разработка (+ правило docs-keep-current)
- [GIT_FLOW.md](GIT_FLOW.md), [RELEASES.md](RELEASES.md) — ветки/релизы
- [todo.md](todo.md) / [completed.md](completed.md)

Контракт HTTP/JSON: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.

## Legacy: Telegram / Mini App

Вся bot-era документация собрана здесь:

→ **[telegram/README.md](telegram/README.md)**

В корне `docs/` остались только stub-редиректы (`MINIAPP.md`, `SETUP*.md`, `SYNC_AUTOMATIC.md`) для старых ссылок.

CI Telegram notifications ≠ user bot.

## Прочее

- [REFACTORING.md](REFACTORING.md) / [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
- [../health-sync-api/README.md](../health-sync-api/README.md)

## Быстрый старт

Корневой [README.md](../README.md) — секция «Быстрый старт (API)».
