# Feature: Boards API seed catalog (list / detail / refresh)

**Status:** In progress  
**Related:** `Документация/Задачи/task-kb-dashboards-platform.md` (этап B minimal), iOS `task-feature-boards-tab-renderer.md`

## Goal

Expose `GET /api/boards`, `GET /api/boards/{id}`, `POST /api/boards/{id}/refresh` so the iOS Overview tab can leave the demo-404 fallback.

## Scope (v1)

- [x] Seed catalog (`boards_catalog.py`) with demo KPI + jobs boards (Structured UI `metric`/`table`)
- [x] Auth via existing Bearer (`get_api_user`)
- [x] Unit + route tests
- [x] **Live board** `car-fuel`: read-only scan of `Документы/Тачки/Соляра/Расходы/Топливо` (`type: fuel`) — no vault writes
- [ ] DB tables / full DSL / remote proxy / agent tools (later)

## Notes

Refresh re-reads vault for `car-fuel`. Path override: `BOARDS_CAR_FUEL_RELATIVE` (under `LOCAL_KB_PATH`).
