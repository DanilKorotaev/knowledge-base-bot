"""MCP server: leased git workspaces under AGENT_ROOT (no HTTP API).

Env:
  AGENT_ROOT   absolute per-user root (required for tools)
  KB_SESSION_ID  optional; used as default session for ensure_workspace
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow `python server.py` from this directory.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from workspace_lib import (
    WorkspaceError,
    ensure_workspace as _ensure,
    list_workspaces as _list,
    release_workspace as _release,
)

mcp = FastMCP("agent-workspaces")


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


@mcp.tool()
def ensure_workspace(
    repo_id: str,
    remote_url: str,
    branch: str = "",
    session_id: str = "",
    ttl_days: int = 7,
) -> str:
    """Ensure a leased git worktree for repo_id under AGENT_ROOT.

    Returns absolute path to the checkout (edit/commit/push there).
    CWD of the agent session stays the vault — do not chdir permanently.
    Personal repo aliases live in the vault skill, not in this tool.
    """
    try:
        result = _ensure(
            repo_id,
            remote_url,
            branch=branch or None,
            session_id=session_id or None,
            ttl_days=ttl_days,
        )
        return _dump(result)
    except WorkspaceError as exc:
        return _dump({"ok": False, "error": str(exc)})


@mcp.tool()
def release_workspace(slot_id: str, delete_worktree: bool = False) -> str:
    """Mark a workspace slot free. Optionally remove the worktree (mirror kept)."""
    try:
        result = _release(slot_id, delete_worktree=delete_worktree)
        return _dump(result)
    except WorkspaceError as exc:
        return _dump({"ok": False, "error": str(exc)})


@mcp.tool()
def workspaces_list() -> str:
    """List mirrors and slots under AGENT_ROOT."""
    try:
        return _dump(_list())
    except WorkspaceError as exc:
        return _dump({"ok": False, "error": str(exc)})


if __name__ == "__main__":
    mcp.run()
