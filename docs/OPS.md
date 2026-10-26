# Operations (current)

Краткая **актуальная** карта деплоя. Устаревшие «подними systemd-бота» гайды — stub или [archive/bot-era/](archive/bot-era/README.md).

## Где что живёт

| Среда | Код | Runtime | Public URL |
|-------|-----|---------|------------|
| **Prod** | host clone (local path) | LaunchAgent **kb-app-api-host** (uvicorn) | `KB_APP_PUBLIC_BASE_URL` in host `.env` / LaunchAgent — not in git |
| **Staging** | staging clone (local path) | Docker Compose `kb-staging-*` | staging public base via env / private ops |

Workflows:

- `.github/workflows/deploy-mac-mini.yml` — prod (ветка `main`)
- `.github/workflows/deploy-mac-mini-staging.yml` — staging

Ветки/релизы: [GIT_FLOW.md](GIT_FLOW.md), [RELEASES.md](RELEASES.md).

## Важно для агентов / CI

- Push на `main`/`develop` может **убить** in-flight Cursor agent на host API — см. `.cursor/rules/deferred-backend-push.mdc`, `no-host-api-restart-mid-query.mdc`.
- Рестарт host API: `scripts/safe-restart-kb-app-api-host.sh` (не `launchctl kickstart -k` mid-reply).
- Public base URL: set on host only; empty export in start scripts must not block dotenv (see `scripts/start-kb-app-api-host.sh`).
- Telegram secrets в CI — **уведомления о деплое**, не user-facing бот ([telegram/](telegram/README.md) deprecated).

## Локально / Docker API

См. [../kb-app-api/README.md](../kb-app-api/README.md), [QUICK_START_DOCKER.md](QUICK_START_DOCKER.md). Feature guides: [kb-app-api/](kb-app-api/README.md).

## Устаревшие / archive

| Файл | Статус |
|------|--------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | stub → этот файл |
| [GITHUB_ACTIONS_DEPLOY.md](GITHUB_ACTIONS_DEPLOY.md) | stub |
| [DEPLOYMENT_SERVER.md](DEPLOYMENT_SERVER.md) | stub → [archive/bot-era/](archive/bot-era/DEPLOYMENT_SERVER.md) |
| Root `NEXT_STEPS.md`, `PUSH_TO_GITHUB.md`, `SETUP_GIT.md` | stubs → archive |
| [telegram/SETUP*.md](telegram/README.md) | legacy bot setup |
