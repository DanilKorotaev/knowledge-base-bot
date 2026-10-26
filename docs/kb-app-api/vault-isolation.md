# Vault & Cursor isolation

**Code:** `kb_app_api/vault_paths.py`, `services/cursor_cli_service.py` (`_soft_jail_*`, `_prepare_env`), admin `cursor_isolation`

## Vault layout

- Host base: `LOCAL_KB_PATH` (resolved absolute).
- Per-user root: `LOCAL_KB_PATH/users/<login>/` via `vault_root_relative` (default from login).
- File IO for App (uploads, boards, health, revert): `resolve_kb_root(user)`.
- Cursor CLI **cwd**: always that same per-user vault when a user is set (`resolve_agent_kb_root`). Isolation mode does **not** change cwd.

Paths must not escape `LOCAL_KB_PATH` (`absolute_vault_root` checks).

## `cursor_isolation`

| Mode | Soft-jail | Intent |
|------|-----------|--------|
| `strict` (default) | On when cwd is `users/<login>/…` | Agent stays inside the vault |
| `host` | Off | Operator mode: may leave the tree if the task needs it |

Soft-jail mechanisms (`CursorCLIService`):

1. Writes `.cursor/rules/vault-isolation.mdc` under the vault (removed for `host`).
2. Prefixes the user query with a short isolation reminder (new chats).

Default for new users: `KB_APP_DEFAULT_CURSOR_ISOLATION` (admin can override on create/patch).

## Env scrub

`cursor-agent` gets a **minimal env** (`_prepare_env`):

- Keep: `PATH`, locale, proxy-related, non-secret `CURSOR_*` / `KB_CURSOR*`, then inject `CURSOR_API_KEY`.
- Drop keys whose names contain substrings like `PASSWORD`, `SECRET`, `TOKEN`, `API_KEY`, `JWT`, `NC_TOKEN`, …

So a multi-user agent cannot `printenv` host API / Nextcloud secrets.

## Sync / DB paths

When the agent reports file changes relative to the vault cwd, helpers rewrite them to `LOCAL_KB_PATH`-relative (`paths_relative_to_base`, `localize_file_changes`) for SyncService / DB.

Nextcloud paths for the App use the user's App Password + `kb_folder` — not `NEXTCLOUD_BOT_*` (see [auth.md](auth.md)).

## Tests

- `kb_app_api/tests/test_vault_paths.py`
- Soft-jail / env: `services/cursor_cli_service.py` (+ related agent prompt tests)

## Related

- [../ARCHITECTURE.md](../ARCHITECTURE.md) § Vault
- Admin field: [admin.md](admin.md)
