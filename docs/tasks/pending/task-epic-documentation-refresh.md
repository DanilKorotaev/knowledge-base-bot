# Epic: Documentation refresh (KB App era)

**Статус:** 📋 Planned  
**Приоритет:** 🔴 Высокий  
**Категория:** Documentation

## Цель

Документация соответствует продукту 2026: **KB App API + per-user vault**. Telegram/Mini App не потерять, но увести в legacy. Подробность по фичам API — отдельно, итерациями (не один присест).

## Принципы

1. **Source of truth** для клиента: iOS `KB_APP_API_CONTRACT` + backend routes; доки репо не спорят с контрактом.
2. Legacy TG: одна папка, одна ссылка из README на Epic revival.
3. После каждого значимого изменения фич — обновлять соответствующий guide (см. правило Cursor).

## Подзадачи

| # | Задача | Исход |
|---|--------|--------|
| 1 | [README primary](../completed/task-doc-readme-kb-app-primary.md) ✅ | Лицо репо |
| 2 | [Relocate Telegram docs](task-doc-relocate-telegram-legacy.md) | Не потерять историю |
| 3 | [ARCHITECTURE refresh](task-doc-architecture-kb-app.md) | Схема multi-user |
| 4 | [Deploy / CI / releases audit](task-doc-deploy-and-releases-audit.md) | Ops правда |
| 5 | [KB App API feature guides](task-doc-kb-app-api-feature-guides.md) | Детали по фичам |
| 6 | [Cursor rule: docs stay current](task-rule-docs-must-stay-current.md) | Процесс |

Старые: `task-doc-api-documentation.md`, `task-doc-improvements.md` — **superseded** этим эпиком (закрыть со ссылкой сюда при выполнении #1).

## Definition of done

- [ ] Новый контрибьютор по README понимает, что поднимать (API), а не бота
- [ ] Telegram docs доступны под `docs/telegram/` (или аналог)
- [ ] Есть индекс фич KB App API
- [ ] Правило в `.cursor/rules` активно
