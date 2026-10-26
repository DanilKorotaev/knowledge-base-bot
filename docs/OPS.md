# Operations (current)

Краткая **актуальная** карта деплоя. Устаревшие «подними systemd-бота» гайды помечены ниже.

## Где что живёт

| Среда | Код | Runtime | URL (типично) |
|-------|-----|---------|----------------|
| **Prod** | host clone (path local) | LaunchAgent **kb-app-api-host** (uvicorn) | set via env / private ops (`KB_APP_PUBLIC_BASE_URL`) |
| **Staging** | staging clone (path local) | Docker Compose `kb-staging-*` | set via env / private ops |

Workflows:

- `.github/workflows/deploy-mac-mini.yml` — prod (ветка `main`)
- `.github/workflows/deploy-mac-mini-staging.yml` — staging

Детали веток/релизов: [GIT_FLOW.md](GIT_FLOW.md), [RELEASES.md](RELEASES.md).

## Важно для агентов / CI

- Push на `main`/`develop` может **убить** in-flight Cursor agent на host API — см. `.cursor/rules/deferred-backend-push.mdc`, `no-host-api-restart-mid-query.mdc`.
- Рестарт host API: `scripts/safe-restart-kb-app-api-host.sh` (не `launchctl kickstart -k` mid-reply).
- Telegram secrets в CI — **уведомления о деплое**, не user-facing бот ([telegram/](telegram/README.md) deprecated).

## Локально / Docker API

См. [../kb-app-api/README.md](../kb-app-api/README.md), [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md).

## Устаревшие документы

| Файл | Статус |
|------|--------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | stub → этот файл; старый текст про bot systemd |
| [GITHUB_ACTIONS_DEPLOY.md](GITHUB_ACTIONS_DEPLOY.md) | stub; описывал `Deploy Bot` / `docker compose bot` |
| [DEPLOYMENT_SERVER.md](DEPLOYMENT_SERVER.md) | проверить; часто bot-era VPS |
| [telegram/SETUP*.md](telegram/README.md) | legacy bot setup |

Аудит-задача (чеклист archive): [task-doc-deploy-and-releases-audit.md](tasks/pending/task-doc-deploy-and-releases-audit.md).
