# Boards: zero-deploy definitions (engine freeze)

**Status:** pending  
**Vault note:** `Документация/Задачи/task-boards-zero-deploy.md`

## Goal

Typical new Overview board = MCP upsert (+ optional vault `.board.py` / recipe) with **no** `knowledge-base-bot` deploy. Deploy only when adding provider/node/sandbox capabilities.

## Near-term

- [ ] Skill/rule: prefer config/`vault_script` over aggregator code changes
- [ ] Richer `vault_script` ctx helpers + optional declarative `.board.json`
- [ ] Freeze new `agg`/features on `vault_*_agg` except bugfixes

## Done already (enablers)
- Definitions in DB; generic frontmatter/json providers
- `vault_script` sandbox; `remote_structured_ui`; Structured UI `metric`/`table`/`chart`
