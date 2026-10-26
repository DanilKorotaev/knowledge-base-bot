# Boards & presets

**Code:** `routes/boards.py`, `boards/`, `boards_catalog.py`, `boards/presets.py`  
**Model:** Postgres/SQLite `kb_app_boards` — composite identity **`(user_id, id)`**

## Product rules

- New users start with **empty** Overview / Actions (`DEFAULT_BOARDS = []` in `boards/seed.py`).
- Domain boards are **not** hardcoded in open-source seed; install presets or `PUT` via agent/MCP.
- Each board belongs to one user; list/detail/archive respect `user_id`.

## Endpoints

Prefix: `/api/boards` (Bearer).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/boards` | Enabled boards for user |
| GET | `/api/boards/presets` | Installable catalog (not yet in DB) |
| POST | `/api/boards/presets/{preset_id}/install` | Copy preset → user board row |
| DELETE | `/api/boards/presets/{preset_id}` | Uninstall that preset board |
| PUT | `/api/boards/order` | `{ ordered_ids }` |
| GET | `/api/boards/archived` | |
| POST | `/api/boards/{id}/archive` \| `…/restore` | |
| GET | `/api/boards/{id}` | Detail + rendered `document` |
| PUT | `/api/boards/{id}` | Upsert definition / static document |
| DELETE | `/api/boards/{id}` | |
| POST | `/api/boards/{id}/refresh` | Recompute live providers |

## Built-in presets (catalog)

Defined in `boards/presets.py` (extend carefully — product copy may be localized):

| id | Surface | Provider |
|----|---------|----------|
| `active-jobs` | actions | `system_query_jobs` |
| `actions-presets` | actions | static placeholder document |

`GET /presets` returns catalog cards (`id`, title, subtitle, icon, kind, surface). Install materializes a full board row for that `user_id`.

## Providers (live)

Under `boards/providers/`:

| Provider | Role |
|----------|------|
| `system_query_jobs` | Active Cursor jobs |
| `vault_frontmatter_agg` | Read-only MD frontmatter aggregates |
| `vault_json_daily_agg` | Daily JSON metrics / charts |
| `vault_script` | Controlled script under vault |
| `remote_structured_ui` | Fetch remote SUI JSON (host allowlist) |
| `static` | Stored `rendered_document` |

Vault providers resolve paths under the **user** `resolve_kb_root` — never write vault files from aggregators (`VaultReadError` on escape).

## iOS contract note

Contract docs historically listed list/detail/refresh only. Presets, archive, order, upsert are live on the API — keep [KB_APP_API_CONTRACT.md](https://github.com/DanilKorotaev/knowledge-base-app-ios/blob/main/docs/KB_APP_API_CONTRACT.md) in sync when the client adopts them.

## Tests

- `kb_app_api/tests/test_boards.py`
- `kb_app_api/tests/test_board_providers_extra.py`
- Fixtures: `kb_app_api/tests/fixtures/board_definitions.py`
