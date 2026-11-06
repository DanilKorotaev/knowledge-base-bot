"""CLI fallback when MCP tools are unavailable (headless cursor-agent)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from workspace_lib import WorkspaceError, ensure_workspace, list_workspaces, release_workspace


def _print(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok", False) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-workspaces")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ensure = sub.add_parser("ensure", help="Ensure leased worktree")
    p_ensure.add_argument("repo_id")
    p_ensure.add_argument("remote_url")
    p_ensure.add_argument("--branch", default="")
    p_ensure.add_argument("--session-id", default="")
    p_ensure.add_argument("--ttl-days", type=int, default=7)

    p_release = sub.add_parser("release", help="Mark slot free")
    p_release.add_argument("slot_id")
    p_release.add_argument("--delete-worktree", action="store_true")

    sub.add_parser("list", help="List mirrors and slots")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "ensure":
            return _print(
                ensure_workspace(
                    args.repo_id,
                    args.remote_url,
                    branch=args.branch or None,
                    session_id=args.session_id or None,
                    ttl_days=args.ttl_days,
                )
            )
        if args.cmd == "release":
            return _print(
                release_workspace(args.slot_id, delete_worktree=args.delete_worktree)
            )
        if args.cmd == "list":
            return _print(list_workspaces())
    except WorkspaceError as exc:
        return _print({"ok": False, "error": str(exc)})
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
