# Feature: Boards API seed catalog (list / detail / refresh)

**Status:** In progress  
**Related:** `Документация/Задачи/task-kb-dashboards-platform.md` (этап B minimal), iOS `task-feature-boards-tab-renderer.md`

## Goal

Expose `GET /api/boards`, `GET /api/boards/{id}`, `POST /api/boards/{id}/refresh` so the iOS Overview tab can leave the demo-404 fallback.

## Scope (v1)

- [x] Seed catalog with demo KPI + jobs + car-fuel
- [x] Auth via existing Bearer (`get_api_user`)
- [x] Unit + route tests
- [x] **DB table** `kb_app_boards` — definition JSON (paths live in DB seed, not provider code)
- [x] Provider `vault_frontmatter_agg` — read-only vault scan from definition
- [ ] Agent tools create/update board
- [ ] vault_script / system / remote / device providers

## Notes

Refresh re-runs the provider. Car-fuel path is only in seeded `definition.path` (editable in DB later without redeploying provider logic).
