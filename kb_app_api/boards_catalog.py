"""Boards catalog API surface — DB-backed definitions + provider runtime."""
from __future__ import annotations

import re
from typing import Any

from kb_app_api.boards import repository, runtime

_BOARD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def validate_board_id(board_id: str) -> str:
    cleaned = str(board_id or "").strip()
    if not _BOARD_ID_RE.match(cleaned):
        raise ValueError(
            "board id must be 1–64 chars: lowercase letters, digits, _ or - "
            "(must start with letter/digit)"
        )
    return cleaned


async def list_boards(
    *,
    include_disabled: bool = False,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    return await runtime.list_boards(include_disabled=include_disabled, user_id=user_id)


async def get_board_detail(
    board_id: str,
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    return await runtime.get_board_detail(
        board_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
    )


async def upsert_board(payload: dict[str, Any]) -> dict[str, Any]:
    """Create or replace a board definition, then return rendered detail."""
    board_id = validate_board_id(str(payload.get("id") or ""))
    await repository.ensure_boards_schema()
    existing = await repository.get_board_row(board_id)

    raw_sort = payload.get("sort_order")
    if existing is None:
        # New boards append to the end unless an explicit positive order is given.
        if raw_sort is None or int(raw_sort or 0) <= 0:
            sort_order = await repository.next_sort_order()
        else:
            sort_order = int(raw_sort)
    elif raw_sort is None:
        sort_order = int(existing.get("sort_order") or 0)
    else:
        sort_order = int(raw_sort)

    row = {
        "id": board_id,
        "title": payload.get("title") or board_id,
        "subtitle": payload.get("subtitle"),
        "icon": payload.get("icon"),
        "kind": payload.get("kind") or "cached_view",
        "sort_order": sort_order,
        "enabled": payload.get("enabled", True),
        "definition": payload.get("definition") or {},
        "list_cell": payload.get("list_cell"),
        "rendered_document": payload.get("rendered_document"),
        "rendered_at": payload.get("rendered_at"),
    }
    await repository.upsert_board_row(row)
    detail = await runtime.get_board_detail(board_id)
    if detail is None:
        stored = await repository.get_board_row(board_id)
        assert stored is not None
        return {
            "board": {
                "id": stored["id"],
                "title": stored["title"],
                "subtitle": stored.get("subtitle"),
                "icon": stored.get("icon"),
                "kind": stored.get("kind"),
                "sort_order": stored.get("sort_order"),
                "enabled": stored.get("enabled"),
                "list_cell": stored.get("list_cell"),
                "rendered_at": stored.get("rendered_at"),
            },
            "document": stored.get("rendered_document")
            or {"schema_version": 1, "screen": {"type": "vstack", "id": "root", "children": []}},
            "rendered_at": stored.get("rendered_at"),
        }
    return detail


async def reorder_boards(ordered_ids: list[str]) -> list[dict[str, Any]]:
    """Persist Overview list order; returns refreshed board list."""
    await repository.set_board_sort_orders(ordered_ids)
    return await runtime.list_boards(include_disabled=False)


async def delete_board(board_id: str) -> bool:
    await repository.ensure_boards_schema()
    return await repository.delete_board_row(board_id)
