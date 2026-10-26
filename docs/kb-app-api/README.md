# KB App API — feature guides (index)

Индекс подробных гайдов. Контракт JSON/путей для iOS:  
`knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`.  
Обзор архитектуры: [../ARCHITECTURE.md](../ARCHITECTURE.md).

**Статус:** guides filled 2026-10-26 — [задача](../tasks/completed/task-doc-kb-app-api-feature-guides.md).

## Guides

| Guide | Routes / packages | Status |
|-------|-------------------|--------|
| [auth.md](auth.md) | `routes/auth`, `routes/me`, NC provision | ✅ |
| [sessions-messages.md](sessions-messages.md) | sessions, messages, attachments, share, files | ✅ |
| [voice-jobs.md](voice-jobs.md) | `voice`, `query_jobs/`, `/api/jobs` | ✅ |
| [boards-presets.md](boards-presets.md) | `boards/`, presets | ✅ |
| [structured-ui.md](structured-ui.md) | `structured_ui/`, ui-events, remote-ui | ✅ |
| [push.md](push.md) | devices, APNs | ✅ |
| [vault-isolation.md](vault-isolation.md) | vault_paths, soft-jail, env scrub | ✅ |
| [health-sync.md](health-sync.md) | `/api/health/sync` | ✅ |
| [admin.md](admin.md) | `/api/admin/users` | ✅ |
| [ops-metrics.md](ops-metrics.md) | `/health`, metrics | ✅ |

## Принцип

Guide = **зачем и как** (потоки, ограничения, ссылки на тесты).  
Схемы полей — в contract / OpenAPI, не копипастить сюда целиком.

При смене поведения API — обновить guide в том же изменении (`.cursor/rules/docs-keep-current.mdc`).
