"""Render boards from DB rows via provider registry."""
from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from config import config

from kb_app_api.boards import repository
from kb_app_api.boards.providers import vault_frontmatter_agg

logger = logging.getLogger(__name__)


def _kb_root() -> Path:
    return Path(config.LOCAL_KB_PATH)


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


def _render_row(
    row: dict[str, Any],
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any] | None:
    definition = row.get("definition") or {}
    provider = str(definition.get("provider") or "").strip()

    if provider == vault_frontmatter_agg.PROVIDER_ID:
        return vault_frontmatter_agg.compute(
            _kb_root(),
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


async def list_boards(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    await repository.ensure_boards_schema()
    rows = await repository.list_board_rows(include_disabled=include_disabled)
    boards: list[dict[str, Any]] = []
    for row in rows:
        if not include_disabled and not row.get("enabled", True):
            continue
        rendered = _render_row(row)
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
) -> dict[str, Any] | None:
    await repository.ensure_boards_schema()
    row = await repository.get_board_row(board_id)
    if row is None:
        return None
    if not row.get("enabled", True):
        return None
    return _render_row(row, period=period, date_from=date_from, date_to=date_to)
