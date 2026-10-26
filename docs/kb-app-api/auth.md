# Auth & Nextcloud identity

**Status:** stub — дополнять по мере изменений.  
**Code:** `kb_app_api/auth_service.py`, `jwt_tokens.py`, `routes/auth.py`, `routes/me.py`, `nextcloud_provision.py`, `nc_token_crypto.py`

## Модель

- App user: `login`, `password_hash`, `role`, `must_change_password`, `vault_root_relative`, `cursor_isolation`, `kb_folder`, `nc_app_password_enc`, optional `telegram_id`
- Tokens: short-lived JWT **access** + opaque **refresh** (`auth_refresh_sessions`)
- Signup: `open_signup` vs invite-only (instance settings / env)

## Основные endpoints

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/auth/signup-status` | public |
| POST | `/api/auth/register` | may provision NC user |
| POST | `/api/auth/login` | mint App Password if missing |
| POST | `/api/auth/refresh` | |
| POST | `/api/auth/logout` | revoke refresh |
| POST | `/api/auth/change-password` | sync NC + remint App Password |
| GET | `/api/auth/me` | `{ "user": { … } }` |
| PATCH | `/api/auth/me` | e.g. `kb_folder` |
| GET/POST | `/api/auth/nc-folders` | picker / create in NC home |

## Nextcloud

- Register/admin create → OCS provision user (same login when possible)
- App Password minted via `getapppassword`, stored encrypted (`KB_NC_TOKEN_KEY`)
- File IO for App: `NextCloudService.for_user` / `SyncService.for_user` — **not** `NEXTCLOUD_BOT_*`
- `kb_folder` — root inside NC home (default `/`)

## Vault

See [../ARCHITECTURE.md](../ARCHITECTURE.md) — `users/<login>/` under `LOCAL_KB_PATH`.

## Tests

- `kb_app_api/tests/test_auth.py`
- `kb_app_api/tests/test_nc_token_crypto.py`
- `kb_app_api/tests/test_vault_paths.py` (local env may need crypto key)

## Related

- Telegram link / invite (planned): [task-epic-telegram-multiuser.md](../tasks/pending/task-epic-telegram-multiuser.md)
- Admin users: `routes/admin_users.py`
