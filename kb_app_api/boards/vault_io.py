"""Read-only vault helpers for board compute.

Never write, unlink, rename, or chmod. Paths must stay under the KB root.
"""
from __future__ import annotations

from pathlib import Path


class VaultReadError(ValueError):
    """Path escapes KB root or is otherwise unsafe to read."""


def resolve_under_root(kb_root: Path, relative: str | Path) -> Path:
    """Resolve ``relative`` under ``kb_root``; raise if it escapes the root."""
    root = kb_root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VaultReadError(f"path escapes KB root: {relative}") from exc
    return candidate


def read_text_under_root(kb_root: Path, relative: str | Path, *, encoding: str = "utf-8") -> str:
    """Read a file under the KB root (read-only open)."""
    path = resolve_under_root(kb_root, relative)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    # Explicit read-only: never open for write.
    with path.open("r", encoding=encoding) as handle:
        return handle.read()


def iter_markdown_files(kb_root: Path, relative_dir: str | Path) -> list[Path]:
    """List ``*.md`` files under a directory (read-only; no writes)."""
    folder = resolve_under_root(kb_root, relative_dir)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*.md") if p.is_file())
