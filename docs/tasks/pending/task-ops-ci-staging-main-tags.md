# Ops: CI staging / main / release tags

**Статус:** 🚧 In progress  
**Приоритет:** 🔴 Высокий (блокер безопасной разработки multi-user)  
**Категория:** CI / Deploy  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`

## Цель

- push **`staging`** → только staging Docker API (`kbapp-staging.example.com`), **prod launchd/API не трогать**
- push **`main`** → prod (`deploy-mac-mini.sh`)
- push **`develop`** → **без** автодеплоя
- tag **`backend/vX.Y.Z`** → prod release + запись в `docs/RELEASES.md`

## Было

`.github/workflows/deploy-mac-mini.yml` на push `develop` катил прод.

## Чеклист

- [x] `deploy-mac-mini.yml` → только `main` (+ tags `backend/v*` + workflow_dispatch)
- [x] `deploy-mac-mini-staging.yml` → ветка `staging`; checkout **`~/Projects/knowledge-base-bot-staging`**
- [x] `scripts/deploy-mac-mini-staging.sh`
- [x] `VERSION` + `docs/RELEASES.md` (скелет); tag deploy via same prod workflow
- [x] `docs/GIT_FLOW.md` + vault [[Mac mini — Ruby и staging]]
- [ ] Создать/запушить `origin/staging` (после merge CI в develop)
- [ ] Bootstrap clone на mini: `~/Projects/knowledge-base-bot-staging`
- [ ] Smoke: push в staging → health staging; prod launchd **не** рестартился

## Не делать

- Править runtime prod руками
- Деплоить multi-user API на prod до приёмки на staging
