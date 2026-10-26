# Doc: KB App API feature guides (detailed)

**Статус:** ✅ Done (guides 2026-10-26)  
**Приоритет:** 🟡 Средний  
**Категория:** Documentation  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)  
**Depends on:** [../completed/task-doc-architecture-kb-app.md](../completed/task-doc-architecture-kb-app.md)

## Что хотим добиться

Подробные гайды **по фичам** (не один гигантский файл). Индекс: `docs/kb-app-api/README.md`.

## Чеклист

- [x] Пройти `kb_app_api/routes/*` → список фич (таблица в индексе)
- [x] Сверить с iOS `KB_APP_API_CONTRACT.md` (дыры отмечены в boards-presets — presets API)
- [x] Создать `docs/kb-app-api/README.md`
- [x] auth, vault-isolation, sessions-messages, voice-jobs, boards-presets, structured-ui, push, health-sync, admin, ops-metrics
- [x] Старый `task-doc-api-documentation.md` — superseded

## Замечание

Не копипастить OpenAPI целиком — guide = **зачем и как**, YAML/contract = схемы.  
Дальше: точечно править guides при смене кода (правило docs-keep-current).
