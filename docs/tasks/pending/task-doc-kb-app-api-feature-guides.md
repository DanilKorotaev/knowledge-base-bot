# Doc: KB App API feature guides (detailed)

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** Documentation  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)  
**Depends on:** [task-doc-architecture-kb-app.md](task-doc-architecture-kb-app.md) (индекс)

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

- [ ] Пройти `kb_app_api/routes/*` → список фич
- [ ] Сверить с iOS `KB_APP_API_CONTRACT.md` (дыры)
- [ ] Создать `docs/kb-app-api/README.md` со статусом «draft / missing»
- [ ] Закрыть/перенаправить старый `task-doc-api-documentation.md`

## Чеклист (фаза 2+ — писать guides)

- [ ] auth + vault-isolation (критично)
- [ ] sessions-messages + query jobs
- [ ] boards-presets
- [ ] остальные по приоритету продукта

## Замечание

Не копипастить OpenAPI целиком — guide = **зачем и как**, YAML/contract = схемы.
