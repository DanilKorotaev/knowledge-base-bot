# Doc: audit deploy / CI / releases docs

**Статус:** 🚧 In progress (OPS.md + stubs на DEPLOYMENT / GHA; archive VPS docs — осталось)  
**Приоритет:** 🟡 Средний  
**Категория:** Documentation / Ops  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)

## Что хотим добиться

Ops-доки описывают **как реально катим сейчас**, без устаревшего «подними бота на VPS и всё».

Файлы-кандидаты (пройти и пометить outdated / fix / move):

- `docs/DEPLOYMENT.md`, `DEPLOYMENT_SERVER.md`, `QUICK_START_DOCKER.md`
- `docs/GITHUB_ACTIONS_DEPLOY.md`, `GIT_FLOW.md`, `RELEASES.md`
- `SETUP_GIT.md`, `PUSH_TO_GITHUB.md`, `NEXT_STEPS.md` (часто мёртвые — archive или delete)
- `scripts/deploy*.sh`, `safe-restart-kb-app-api-host.sh` — кратко задокументировать в ops index
- Правило: push `develop`/`main` убивает agent на Mac mini — уже в `.cursor/rules`, продублировать в deploy doc

## Чеклист

- [x] Таблица «что куда деплоится» → [OPS.md](../../OPS.md)
- [x] Stub устаревших DEPLOYMENT.md / GITHUB_ACTIONS_DEPLOY.md
- [ ] DEPLOYMENT_SERVER.md / NEXT_STEPS / PUSH_TO_GITHUB — archive или stub
- [ ] RELEASES / CHANGELOG: кто пишет (CI vs вручную) — сверить с prepare_release
- [x] Telegram: CI notify ≠ user bot (отмечено в OPS + telegram/)

## Критерий

Новый админ по докам может задеплоить API на staging без чтения чужих чатов.
