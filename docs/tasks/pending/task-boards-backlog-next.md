# Boards / Overview — backlog

## Done recently
- Empty open-source seed; definitions via MCP/DB
- Generic `vault_frontmatter_agg` + optional `sidecar`
- Generic `vault_json_daily_agg` (HealthData daily/workouts JSON)
- `period` + `from`/`to` + `period_ui` on boards
- Auto-invalidate list cache after agent writes / Health sync
- iOS: range calendar, Overview toggle, localized table dates + rendered_at
- MCP `kb-boards` + vault rule/skill
- Live boards: car-fuel / fines / TO / workouts / health

## Still open
1. In-app chat-agent tools (optional — MCP on mini already covers Cursor)
2. Multi-user bearer for MCP (later)
3. Web client / admin CRUD

## Done this slice
- System board provider `system_query_jobs` + `GET /api/jobs/active` + `DELETE /api/jobs/{id}`
- Charts: Structured UI `chart` node + `charts[]` on `vault_json_daily_agg`
- `vault_script` (sandboxed `.board.py` under vault)
- `remote_structured_ui` (HTTPS + `BOARDS_REMOTE_HOST_ALLOWLIST`)
- iOS: chart rendering + cancel job from board buttons
