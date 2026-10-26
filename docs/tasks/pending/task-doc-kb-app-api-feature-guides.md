# Doc: KB App API feature guides (detailed)

**Статус:** 🚧 In progress (индекс + auth stub)  
**Приоритет:** 🟡 Средний  
**Категория:** Documentation  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)  
**Depends on:** [../completed/task-doc-architecture-kb-app.md](../completed/task-doc-architecture-kb-app.md)

## Что хотим добиться

Подробные гайды **по фичам** (не один гигантский файл). Итеративно: сначала инвентаризация, потом по одному guide.

Предлагаемый индекс `docs/kb-app-api/README.md`:

| Guide | Содержание |
|-------|------------|
| `auth.md` | JWT, refresh, register/invite, NC App Password, kb_folder |
| `sessions-messages.md` | CRUD sessions, compose, SSE, query jobs |
| `boards-presets.md` | per-user boards, presets install, surfaces |
| `structured-ui.md` | schema, agent, channel differences |
| `push.md` | device tokens, APNs env |
| `vault-isolation.md` | strict/host, soft-jail, env scrub |
| `health-sync.md` | связь с health-sync-api |
| `admin.md` | admin users (когда будет) |

Каждый guide: endpoints, модель данных, ограничения, ссылка на тесты / contract.

## Чеклист (фаза 1 — инвентарь)

- [x] Пройти `kb_app_api/routes/*` → список фич (таблица в индексе)
- [ ] Сверить с iOS `KB_APP_API_CONTRACT.md` (дыры)
- [x] Создать `docs/kb-app-api/README.md` со статусом «draft / missing»
- [x] Старый `task-doc-api-documentation.md` — superseded

## Чеклист (фаза 2+ — писать guides)

- [x] auth stub (`docs/kb-app-api/auth.md`)
- [ ] vault-isolation
- [ ] sessions-messages + query jobs
- [ ] boards-presets
- [ ] остальные по приоритету продукта

## Замечание

Не копипастить OpenAPI целиком — guide = **зачем и как**, YAML/contract = схемы.
