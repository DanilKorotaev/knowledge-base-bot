# Boards / Overview — backlog

## Done
- Empty OSS seed; definitions via MCP/DB
- Providers: `vault_frontmatter_agg` (+ sidecar), `vault_json_daily_agg`, `vault_script`, `remote_structured_ui`, `system_query_jobs`, `static`
- Period: `period` + `from`/`to` + `period_ui`
- Auto-invalidate list cache after agent / Health writes
- Charts (`chart` node + `charts[]`); median agg / median unit price
- Jobs board + cancel API; iOS cancel buttons
- Overview drag-reorder → `PUT /api/boards/order`; new boards append at end
- Live boards: health, car-*, workouts, active-jobs
- MCP `kb-boards` + skill/rule

## In progress
1. **Archive boards** — API + iOS wired; needs deploy + manual check → vault `task-boards-archive.md`

## Still open
2. **Zero-deploy boards** — new board = MCP + vault script/recipe, no API deploy for typical KPI → vault `task-boards-zero-deploy.md`
3. In-app chat-agent boards tools (optional; MCP on mini covers Cursor)
4. Multi-user bearer for MCP (later)
5. Web / admin CRUD (later)

## Direction note
Prefer extending **definitions + `vault_script`** over new Python in aggregators. Backend deploy only for new provider/node/sandbox.
