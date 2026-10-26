# Документация

Продукт репозитория — **Knowledge Base App backend** (`kb_app_api`).  
Telegram-бот и Mini App — **deprecated**; revival: [tasks/pending/task-epic-telegram-multiuser.md](tasks/pending/task-epic-telegram-multiuser.md).

Обновление всей док-базы: [tasks/pending/task-epic-documentation-refresh.md](tasks/pending/task-epic-documentation-refresh.md).

## Актуальный фокус (KB App)

- [../kb-app-api/README.md](../kb-app-api/README.md) — Docker / health / auth notes для API
- [ARCHITECTURE.md](ARCHITECTURE.md) — пока ещё bot-centric; refresh → [task-doc-architecture-kb-app.md](tasks/pending/task-doc-architecture-kb-app.md)
- [DEVELOPMENT.md](DEVELOPMENT.md) — разработка
- [DEPLOYMENT.md](DEPLOYMENT.md), [GITHUB_ACTIONS_DEPLOY.md](GITHUB_ACTIONS_DEPLOY.md), [GIT_FLOW.md](GIT_FLOW.md) — ops (аудит → [task-doc-deploy-and-releases-audit.md](tasks/pending/task-doc-deploy-and-releases-audit.md))
- [todo.md](todo.md) / [completed.md](completed.md) — задачи
- Feature guides API (planned): [task-doc-kb-app-api-feature-guides.md](tasks/pending/task-doc-kb-app-api-feature-guides.md)

Контракт HTTP/JSON для iOS живёт в репозитории приложения: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.

## Deprecated: Telegram / Mini App

Не использовать как primary onboarding. Код и старые гайды сохранены:

- [MINIAPP.md](MINIAPP.md) — Telegram Mini App (перенос в `docs/telegram/` → [task-doc-relocate-telegram-legacy.md](tasks/pending/task-doc-relocate-telegram-legacy.md))
- [SETUP.md](SETUP.md), [SETUP_NEXTCLOUD.md](SETUP_NEXTCLOUD.md), [SETUP_NEXTCLOUD_SCENARIO.md](SETUP_NEXTCLOUD_SCENARIO.md) — в основном bot-era setup
- [SYNC_AUTOMATIC.md](SYNC_AUTOMATIC.md) — sync notes (частично пересекается с App Password path)

CI Telegram notifications ≠ user bot.

## Прочее

- [REFACTORING.md](REFACTORING.md) / [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)
- [../health-sync-api/README.md](../health-sync-api/README.md)

## Быстрый старт

См. корневой [README.md](../README.md) — секция «Быстрый старт (API)».
