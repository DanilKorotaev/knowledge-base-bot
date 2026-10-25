# API: auth + Nextcloud-unified users

**Статус:** 🚧 In progress (MVP на staging 2026-10-24, `088e771`)  
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
- Per-user App Password: mint via `GET …/ocs/v2.php/core/getapppassword` (login password), store encrypted (`nc_app_password_enc`, key `KB_NC_TOKEN_KEY`)
- Remint on `change-password`; bot does **not** share all KBs — file access via user App Password + `kb_folder` (default `/`)
- Soft-lock: смена пароля NC только через наш API (не через NC UI) — вне v1 UI

## Чеклист

- [x] Миграции Postgres/SQLite (+ `auth_refresh_sessions`)
- [x] Password hashing (stdlib scrypt)
- [x] JWT access + opaque refresh
- [x] NC provision service (`kb_app_api/nextcloud_provision.py`)
- [x] `get_api_user` из access token → real user
- [x] Shared Bearer убран из deps; unit-тесты переведены на register/login
- [x] Staging smoke: register + `kbadmin` login (2026-10-24)
- [x] `nc_app_password_enc` + `kb_folder`; mint/rotate; `PATCH /api/auth/me`
- [ ] Полный per-user `vault_root` во всех call sites (`health_sync`, `boards/runtime`, `voice_attachments`, `revert_helpers`) — частично (messages uploads)
- [ ] WebDAV sync через per-user App Password (следующий шаг)
- [ ] E2E iOS: login тестовым юзером вместо `KB_APP_API_TOKEN`
- [x] Обновить `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md` (JWT auth v1.2 + kb_folder)

## Вне скоупа здесь

Admin UI, Telegram, provider keys UI
