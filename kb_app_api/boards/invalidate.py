"""Refresh board list_cell cache when vault files under a board path change."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from kb_app_api.boards import repository, runtime

logger = logging.getLogger(__name__)


def _normalize_rel(path: str) -> str:
    return str(path or "").replace("\\", "/").lstrip("./").strip()


def _board_watch_prefixes(definition: dict[str, Any]) -> list[str]:
    prefixes: list[str] = []
    main = _normalize_rel(str(definition.get("path") or ""))
    if main:
        prefixes.append(main)
    sources = definition.get("sources")
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict):
                p = _normalize_rel(str(src.get("path") or ""))
                if p:
                    prefixes.append(p)
    sidecar = definition.get("sidecar")
    if isinstance(sidecar, dict):
        p = _normalize_rel(str(sidecar.get("path") or ""))
        if p:
            prefixes.append(p)
    return prefixes


def _path_matches(rel_path: str, prefixes: list[str]) -> bool:
    rel = _normalize_rel(rel_path)
    if not rel or not prefixes:
        return False
    for prefix in prefixes:
        if rel == prefix or rel.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


async def invalidate_boards_for_paths(changed_paths: list[str]) -> list[str]:
    """Recompute + persist list_cell for boards whose vault paths intersect changes.

    Detail GET already live-reads vault; this keeps Overview list cards fresh in DB
    and bumps ``rendered_at`` after agent/Health writes.
    """
    cleaned = [_normalize_rel(p) for p in changed_paths if _normalize_rel(p)]
    if not cleaned:
        return []

    await repository.ensure_boards_schema()
    rows = await repository.list_board_rows(include_disabled=True)
    touched: list[str] = []
    for row in rows:
        if not row.get("enabled", True):
            continue
        definition = row.get("definition") or {}
        prefixes = _board_watch_prefixes(definition if isinstance(definition, dict) else {})
        if not any(_path_matches(p, prefixes) for p in cleaned):
            continue
        rendered = await runtime._render_row(row)  # noqa: SLF001 — shared render path
        if rendered is None:
            continue
        board = rendered.get("board") or {}
        payload = {
            "id": row["id"],
            "title": row.get("title") or row["id"],
            "subtitle": row.get("subtitle"),
            "icon": row.get("icon"),
            "kind": row.get("kind") or "cached_view",
            "sort_order": row.get("sort_order") or 0,
            "enabled": row.get("enabled", True),
            "definition": definition,
            "list_cell": board.get("list_cell"),
            "rendered_document": rendered.get("document"),
            "rendered_at": rendered.get("rendered_at") or board.get("rendered_at"),
        }
        await repository.upsert_board_row(payload)
        touched.append(str(row["id"]))
        logger.info("boards invalidate: refreshed %s", row["id"])
    return touched


def maybe_invalidate_boards_for_kb_changes(kb_root: Path | str, changes: list[dict[str, Any]]) -> None:
    """Sync wrapper used from write hooks — schedules async work when a loop is running."""
    _ = kb_root
    paths = [str(c.get("path") or "") for c in changes if isinstance(c, dict)]
    if not paths:
        return
    try:
        import asyncio

        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run() -> None:
        try:
            await invalidate_boards_for_paths(paths)
        except Exception:
            logger.warning("boards invalidate failed", exc_info=True)

    loop.create_task(_run())
