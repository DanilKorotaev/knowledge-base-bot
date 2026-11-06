# Agent workspaces MCP

Leased git checkouts under per-user `AGENT_ROOT` so KB App / mini agents do not edit nested `.git` copies inside the vault.

## Layout

```
$AGENT_ROOT/workspaces/
  mirrors/<repo_id>.git/   # bare
  slots/<slot_id>/
    repo/                  # worktree — edit here
    lease.json
```

## Tools

| Tool | Purpose |
|------|---------|
| `ensure_workspace` | Fetch mirror + lease worktree; returns absolute `path` |
| `release_workspace` | Mark slot free (optional delete worktree) |
| `workspaces_list` | List mirrors/slots |

## Env

- `AGENT_ROOT` — required, absolute, per-user
- `KB_SESSION_ID` — optional default for lease reuse

Personal `repo_id` → remote aliases belong in the **vault skill**, not here.

## CLI

```bash
export AGENT_ROOT=/path/to/user/agent-root
bash mcp-servers/agent-workspaces/cli.sh ensure bot git@github.com:org/repo.git --branch develop
bash mcp-servers/agent-workspaces/cli.sh list
```
