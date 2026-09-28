# Boards / Overview — backlog

## Done
- Empty OSS seed; definitions via MCP/DB
- Providers: `vault_frontmatter_agg` (+ sidecar), `vault_json_daily_agg`, `vault_script` (.py/.json/.sh), `remote_structured_ui`, `system_query_jobs`, `static`
- Period / charts / median / jobs cancel / reorder / archive API
- Live boards via MCP; skill + zero-deploy rule
- In-app chat boards path: skill + `mcp-servers/kb-boards/cli.sh` (+ MCP when available)

## Still open
1. Migrate special KPI logic off aggregators onto vault scripts (freeze `vault_*_agg` features)
2. Richer script `ctx` / declarative compose
3. Multi-user bearer for MCP (later)
4. Web / admin CRUD (later)

## Direction
New board = MCP/CLI + vault script/recipe. Backend deploy only for new provider/node/sandbox.
