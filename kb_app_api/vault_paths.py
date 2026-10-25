"""Per-user vault root under LOCAL_KB_PATH/users/{login}."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config import config


def kb_base() -> Path:
    return Path(config.LOCAL_KB_PATH).resolve()


def vault_relative_for_login(login: str) -> str:
    safe = "".join(c for c in login.strip() if c.isalnum() or c in ("-", "_", ".")).strip(".-_")
    if not safe:
        raise ValueError("invalid login for vault path")
    return f"users/{safe}"


def absolute_vault_root(user: dict[str, Any]) -> Path:
    rel = (user.get("vault_root_relative") or "").strip().lstrip("/")
    if not rel:
        login = (user.get("login") or f"id{user.get('id')}").strip()
        rel = vault_relative_for_login(login)
    root = (kb_base() / rel).resolve()
    base = kb_base()
    if root != base and base not in root.parents:
        raise ValueError("vault_root escapes LOCAL_KB_PATH")
    return root


def ensure_vault_dir(user: dict[str, Any]) -> Path:
    root = absolute_vault_root(user)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_kb_root(user: dict[str, Any] | None = None) -> Path:
    """Absolute vault for file IO (uploads, health, boards, revert)."""
    if user is None:
        return kb_base()
    if user.get("vault_root"):
        return Path(str(user["vault_root"])).resolve()
    return absolute_vault_root(user)


def resolve_agent_kb_root(user: dict[str, Any] | None = None) -> Path:
    """
    Cursor CLI cwd for this user.
    cursor_isolation=strict → only vault; host → whole LOCAL_KB_PATH (legacy mini).
    """
    if user is None:
        return kb_base()
    isolation = (user.get("cursor_isolation") or "strict").strip().lower()
    if isolation == "host":
        return kb_base()
    return resolve_kb_root(user)


def paths_relative_to_base(kb_path: Path, relative_paths: list[str]) -> list[str]:
    """Rewrite vault-relative paths to LOCAL_KB_PATH-relative (for SyncService / DB)."""
    base = kb_base()
    root = Path(kb_path).resolve()
    try:
        prefix = str(root.relative_to(base)).replace("\\", "/")
    except ValueError:
        return list(relative_paths)
    if not prefix or prefix == ".":
        return list(relative_paths)
    out: list[str] = []
    for raw in relative_paths:
        path = (raw or "").strip().lstrip("/")
        if not path:
            out.append(path)
            continue
        if path == prefix or path.startswith(prefix + "/"):
            out.append(path)
        else:
            out.append(f"{prefix}/{path}")
    return out


def localize_file_changes(changes: list[dict[str, Any]], kb_path: Path) -> list[dict[str, Any]]:
    """Prefix change paths so they are relative to LOCAL_KB_PATH when agent cwd is a vault."""
    if not changes:
        return changes
    paths = [str(c.get("path") or "") for c in changes]
    rewritten = paths_relative_to_base(kb_path, paths)
    out: list[dict[str, Any]] = []
    for change, new_path in zip(changes, rewritten):
        item = dict(change)
        item["path"] = new_path
        out.append(item)
    return out


def vault_prefix_for_user(user: dict[str, Any]) -> str:
    rel = (user.get("vault_root_relative") or "").strip().lstrip("/")
    if rel:
        return rel
    login = (user.get("login") or "").strip()
    if login:
        return vault_relative_for_login(login)
    return ""


def to_vault_relative(user: dict[str, Any], path: str) -> str:
    """
    Strip ``users/{login}/`` (or vault_root_relative) from a LOCAL_KB_PATH-relative path.

    Paths already under the vault (or outside it) are returned stripped of leading ``/``.
    """
    raw = (path or "").strip().lstrip("/")
    prefix = vault_prefix_for_user(user)
    if not prefix or not raw:
        return raw
    if raw == prefix:
        return ""
    if raw.startswith(prefix + "/"):
        return raw[len(prefix) + 1 :]
    return raw


def changes_to_vault_relative(
    user: dict[str, Any], changes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Rewrite change ``path`` fields for SyncService.for_user (vault-relative)."""
    out: list[dict[str, Any]] = []
    for change in changes:
        item = dict(change)
        item["path"] = to_vault_relative(user, str(change.get("path") or ""))
        out.append(item)
    return out
