# API: auth + Nextcloud-unified users

**Статус:** 📋 Planned  
**Приоритет:** 🔴 Высокий  
**Категория:** kb_app_api / Auth  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** staging CI (`task-ops-ci-staging-main-tags`) — катить только на staging

## Цель

Внутренние пользователи KB (не Telegram): login/password, JWT access+refresh, создание NC-user с тем же login/password, per-user `vault_root`. Удалить shared Bearer.

## Модель

- `users`: `login`, `password_hash`, `email`, `role`, `must_change_password`, `nextcloud_username`, `vault_root_relative`, `quota_bytes`, `cursor_isolation` (`strict`|`host`)
- `auth_sessions` (refresh), `auth_email_tokens`, `instance_settings` (`open_signup`|`invite_only`, defaults)
- `LOCAL_KB_BASE/users/{login}/` вместо одного `LOCAL_KB_PATH` для API-пути

## Endpoints

- `POST /api/auth/register` (если open_signup)
- `POST /api/auth/login` → access + refresh
- `POST /api/auth/refresh`, `/logout`
- `POST /api/auth/change-password` → KB + NC Provisioning API
- `GET /api/auth/me`
- Удалить: shared `KB_APP_API_TOKEN` gate, `POST /api/auth/token` (issue secret), зависимость от `KB_APP_API_TELEGRAM_ID` для app traffic

## NC

- Create user via OCS Provisioning (или `occ` на host) при register/admin create
- Set quota; password sync только через наши ручки

## Чеклист

- [ ] Миграции Postgres/SQLite
- [ ] Password hashing (argon2/bcrypt)
- [ ] JWT access + opaque/rotating refresh
- [ ] NC provision service
- [ ] `get_api_user` из access token → real user; все routes используют `vault_root`
- [ ] Убрать shared Bearer из deps, config, tests, contract, env.example
- [ ] E2E: login тестовым юзером вместо `KB_APP_API_TOKEN`
- [ ] Обновить `docs/KB_APP_API_CONTRACT.md` (и iOS копию при sync)
- [ ] Катить и проверить **только staging**

## Вне скоупа здесь

Admin UI, Telegram, provider keys UI
