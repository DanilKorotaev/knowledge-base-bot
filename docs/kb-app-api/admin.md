# Admin users

**Code:** `routes/admin_users.py`  
**Auth:** `require_admin` (JWT user with `role=admin`)

## Endpoints

Prefix: `/api/admin/users`.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/admin/users` | List |
| POST | `/api/admin/users` | Create (`login`, `role`, optional `cursor_isolation`, …) — may provision NC |
| PATCH | `/api/admin/users/{user_id}` | Patch role / isolation / flags |
| POST | `/api/admin/users/{user_id}/reset-password` | Issue temporary password |

Public user fields include `cursor_isolation`, `vault_root_relative`, role, etc. (no password hashes).

Default isolation for creates: `KB_APP_DEFAULT_CURSOR_ISOLATION` unless body overrides (`strict` \| `host`).

## Admin web

If `admin-web/` is present, FastAPI mounts static UI at `/admin/` (`main.py`).

Broader admin REST / web epic: [task-api-admin-rest-and-web.md](../tasks/pending/task-api-admin-rest-and-web.md).

## Tests

- `kb_app_api/tests/test_admin_users.py`
