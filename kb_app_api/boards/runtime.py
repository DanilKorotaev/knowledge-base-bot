"""Render boards from DB rows via provider registry."""
from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from kb_app_api.boards import repository
from kb_app_api.boards.providers import (
    remote_structured_ui,
    system_query_jobs,
    vault_frontmatter_agg,
    vault_json_daily_agg,
    vault_script,
)
from kb_app_api.vault_paths import kb_base, resolve_kb_root

logger = logging.getLogger(__name__)


def _kb_root(kb_root: Path | None = None) -> Path:
    return Path(kb_root) if kb_root is not None else kb_base()


async def _kb_root_for_user(user_id: int | None, kb_root: Path | None = None) -> Path:
    if kb_root is not None:
        return Path(kb_root)
    if user_id is None:
        return kb_base()
    from utils.db_helpers import get_db

    db = await get_db()
    user = await db.get_user_by_id(user_id)
    return resolve_kb_root(user) if user else kb_base()


def _public_board(
    row: dict[str, Any],
    *,
    list_cell: dict[str, Any] | None = None,
    rendered_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "subtitle": row.get("subtitle"),
        "icon": row.get("icon"),
        "kind": row.get("kind") or "cached_view",
        "sort_order": int(row.get("sort_order") or 0),
        "enabled": bool(row.get("enabled", True)),
        "list_cell": list_cell if list_cell is not None else row.get("list_cell"),
        "rendered_at": rendered_at if rendered_at is not None else row.get("rendered_at"),
    }


def public_board_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Board list payload from a DB row without re-running providers."""
    return _public_board(row)


async def list_archived_boards(*, user_id: int | None = None) -> list[dict[str, Any]]:
    """Disabled boards for the Archive screen (cached list_cell only)."""
    await repository.ensure_boards_schema()
    rows = await repository.list_board_rows(include_disabled=True, user_id=user_id)
    boards = [
        _public_board(row)
        for row in rows
        if not row.get("enabled", True)
    ]
    boards.sort(key=lambda b: (str(b.get("title") or "").lower(), str(b.get("id") or "")))
    return boards


async def _render_row(
    row: dict[str, Any],
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: int | None = None,
    kb_root: Path | None = None,
) -> dict[str, Any] | None:
    definition = row.get("definition") or {}
    provider = str(definition.get("provider") or "").strip()
    root = await _kb_root_for_user(user_id, kb_root)

    if provider == vault_frontmatter_agg.PROVIDER_ID:
        return vault_frontmatter_agg.compute(
            root,
            row,
            definition,
            period=period,
            date_from=date_from,
            date_to=date_to,
        )

    if provider == vault_json_daily_agg.PROVIDER_ID:
        return vault_json_daily_agg.compute(
            root,
            row,
            definition,
            period=period,
            date_from=date_from,
            date_to=date_to,
        )

    if provider == system_query_jobs.PROVIDER_ID:
        return await system_query_jobs.compute(row, definition, user_id=user_id)

    if provider == remote_structured_ui.PROVIDER_ID:
        return remote_structured_ui.compute(row, definition)

    if provider == vault_script.PROVIDER_ID:
        return vault_script.compute(
            root,
            row,
            definition,
            period=period,
            date_from=date_from,
            date_to=date_to,
        )

    if provider == "static" or not provider:
        document = row.get("rendered_document")
        if not isinstance(document, dict):
            return None
        period_ui = str(definition.get("period_ui") or "none").strip().lower()
        if period_ui not in ("none", "month", "range"):
            period_ui = "none"
        board = _public_board(row)
        board["period_ui"] = period_ui
        scoped = bool(date_from or date_to)
        return {
            "board": board,
            "document": deepcopy(document),
            "rendered_at": row.get("rendered_at"),
            "period": period or ("range" if scoped else "all"),
            "from": date_from,
            "to": date_to,
        }

    logger.warning("unknown board provider %r for %s", provider, row.get("id"))
    return None


async def list_boards(
    *,
    include_disabled: bool = False,
    user_id: int | None = None,
    kb_root: Path | None = None,
) -> list[dict[str, Any]]:
    await repository.ensure_boards_schema()
    rows = await repository.list_board_rows(
        include_disabled=include_disabled,
        user_id=user_id,
    )
    root = await _kb_root_for_user(user_id, kb_root)
    boards: list[dict[str, Any]] = []
    for row in rows:
        if not include_disabled and not row.get("enabled", True):
            continue
        rendered = await _render_row(row, user_id=user_id, kb_root=root)
        if rendered is None:
            continue
        boards.append(deepcopy(rendered["board"]))
    boards.sort(key=lambda b: int(b.get("sort_order") or 0))
    return boards


async def get_board_detail(
    board_id: str,
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: int | None = None,
    kb_root: Path | None = None,
) -> dict[str, Any] | None:
    await repository.ensure_boards_schema()
    row = await repository.get_board_row(board_id, user_id=user_id)
    if row is None:
        return None
    if not row.get("enabled", True):
        return None
    return await _render_row(
        row,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        kb_root=await _kb_root_for_user(user_id, kb_root),
    )
