# Rule: keep documentation current with code

**Статус:** ✅ Done (rule + DEVELOPMENT mention; optional CI later)  
**Приоритет:** 🔴 Высокий  
**Категория:** Process / Cursor  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)

## Цель

Агенты и люди **не оставляют доки гнить**: при изменении поведения API/деплоя/auth обновляют соответствующий guide или явно заводят follow-up task.

## Чеклист

- [x] Добавить `.cursor/rules/docs-keep-current.mdc`
- [x] Упомянуть в `docs/DEVELOPMENT.md` одной фразой
- [ ] (Optional later) CI: fail if `kb_app_api/routes` changed without touch `docs/kb-app-api/` or contract — только после появления guides

## Черновик правила

```markdown
# Documentation stays current

When you change user-facing or ops-facing behavior in this repo:

1. Update the matching doc in the same change (README, docs/kb-app-api/*,
   docs/ARCHITECTURE.md, deploy docs, or iOS KB_APP_API_CONTRACT if API shape).
2. If the right guide does not exist yet, add a checkbox follow-up under
   task-doc-kb-app-api-feature-guides.md — do not silently skip.
3. Telegram/Mini App docs live under docs/telegram/ (legacy); do not revive
   bot-primary wording in root README.
4. Before finishing a PR that touches kb_app_api/** or deploy scripts: skim
   whether README/ARCHITECTURE still tell the truth.
```

## Не делать

- Требовать полный rewrite docs на каждый typo-fix
- Блокировать hotfix без docs, если follow-up task создан в том же PR
