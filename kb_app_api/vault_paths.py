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
