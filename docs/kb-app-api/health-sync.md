# Health sync

**Code:** `routes/health_sync.py`, `health_paths.py`, user setting `health_data_relative` (`routes/me.py`)

Writes Apple Health (or similar) JSON exports into the **user vault**, then optionally syncs those paths to Nextcloud with the user's App Password.

## Endpoints

Prefix: `/api/health/sync` (Bearer).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/health/sync/state` | Reads `sync_state.json` under health folder → 404 if missing |
| POST | `/api/health/sync/files` | Body: `{ files: [{ path, content_base64 }] }` |

Limits: max 100 files / request; max 10 MiB / file. Paths must stay under the user's health folder (`validate_health_file_path` — no `..`).

Response: `{ written: […], synced_to_nextcloud: bool }`.

## Vault layout

- Root: `resolve_kb_root(user)` + `health_data_relative` from user prefs (PATCH `/api/me` / health fields).
- Relative paths in the API are relative to that health folder, not vault root.

## Related services

Standalone **health-sync-api** (if deployed) is a sibling product; this guide covers the KB App API surface only. Contract details for Health clients may live outside this repo.

## Tests

- Prefer path validation + route tests under `kb_app_api/tests/` when present
