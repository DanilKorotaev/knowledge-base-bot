# Feature: Boards API seed catalog (list / detail / refresh)

**Status:** In progress  
**Related:** `Документация/Задачи/task-kb-dashboards-platform.md` (этап B minimal), iOS `task-feature-boards-tab-renderer.md`

## Goal

Expose `GET /api/boards`, `GET /api/boards/{id}`, `POST /api/boards/{id}/refresh` so the iOS Overview tab can leave the demo-404 fallback.

## Scope (v1)

- [x] Seed catalog (`boards_catalog.py`) with demo KPI + jobs boards (Structured UI `metric`/`table`)
- [x] Auth via existing Bearer (`get_api_user`)
- [x] Unit + route tests
- [ ] DB tables / vault compute DSL / remote proxy / agent tools (later)

## Notes

Refresh is a no-op recompute for seed data. Real cache invalidation comes with vault compute.
