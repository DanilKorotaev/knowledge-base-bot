# KB App API — feature guides (index)

Индекс подробных гайдов. Контракт JSON/путей для iOS:  
`knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.  
Обзор архитектуры: [../ARCHITECTURE.md](../ARCHITECTURE.md).

**Статус инвентаря:** draft (2026-10-26). Гайды пишутся итеративно — [задача](../tasks/pending/task-doc-kb-app-api-feature-guides.md).

## Routes → planned guides

| Guide | Routes / packages | Status |
|-------|-------------------|--------|
| [auth.md](auth.md) | `routes/auth`, `routes/me`, `auth_service`, NC provision | 🚧 stub |
| sessions-messages | `sessions`, `messages`, `attachments`, `compose`, `share` | 📋 missing |
| voice-jobs | `voice`, `query_jobs/` | 📋 missing |
| boards-presets | `boards/`, `routes/boards` | 📋 missing |
| structured-ui | `structured_ui/`, `ui_events`, `remote_ui` | 📋 missing |
| push | `devices`, `apns_push_service`, `push_dispatch` | 📋 missing |
| vault-isolation | `vault_paths`, cursor soft-jail, env scrub | 📋 missing |
| health-sync | `routes/health_sync`, health-sync-api | 📋 missing |
| admin | `routes/admin_users` | 📋 missing |
| ops-metrics | `health`, `metrics` | 📋 missing |

## Принцип

Guide = **зачем и как** (потоки, ограничения, ссылки на тесты).  
Схемы полей — в contract / OpenAPI, не копипастить сюда целиком.
