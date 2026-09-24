# Feature: Boards API + DB definitions + MCP upsert

**Status:** In progress  
**Related:** `Документация/Задачи/task-kb-dashboards-platform.md` (этап B/F), iOS `task-feature-boards-tab-renderer.md`

## Goal

Expose boards HTTP API for iOS Overview; definitions in DB; **no domain boards in open-source seed**. Agents create boards via **MCP** (`mcp-servers/kb-boards`) → `PUT /api/boards/{id}`.

## Scope

- [x] `GET /api/boards`, `GET /api/boards/{id}`, `POST …/refresh`
- [x] `PUT /api/boards/{id}`, `DELETE /api/boards/{id}`
- [x] Auth via existing Bearer (`get_api_user`)
- [x] DB table `kb_app_boards` — definition JSON
- [x] Provider `vault_frontmatter_agg` — read-only vault scan from definition (dotted fields)
- [x] `DEFAULT_BOARDS = []` — examples only in `tests/fixtures/board_definitions.py`
- [x] MCP `kb-boards` + Cursor skill `.cursor/skills/kb-boards`
- [ ] Period / month picker on board detail (deferred — refresh only for now)
- [ ] In-app chat-agent tools (after MCP)
- [ ] Settings toggle for Overview tab (like Health)
- [ ] vault_script / system / remote / device providers

## Notes

Existing installs keep rows already in DB (seed never deletes). Fresh OSS clones start with an empty Overview until MCP upsert.
