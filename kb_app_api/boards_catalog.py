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


async def list_boards(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    return await runtime.list_boards(include_disabled=include_disabled)


async def get_board_detail(board_id: str) -> dict[str, Any] | None:
    return await runtime.get_board_detail(board_id)


async def upsert_board(payload: dict[str, Any]) -> dict[str, Any]:
    """Create or replace a board definition, then return rendered detail."""
    board_id = validate_board_id(str(payload.get("id") or ""))
    row = {
        "id": board_id,
        "title": payload.get("title") or board_id,
        "subtitle": payload.get("subtitle"),
        "icon": payload.get("icon"),
        "kind": payload.get("kind") or "cached_view",
        "sort_order": int(payload.get("sort_order") or 0),
        "enabled": payload.get("enabled", True),
        "definition": payload.get("definition") or {},
        "list_cell": payload.get("list_cell"),
        "rendered_document": payload.get("rendered_document"),
        "rendered_at": payload.get("rendered_at"),
    }
    await repository.ensure_boards_schema()
    await repository.upsert_board_row(row)
    detail = await runtime.get_board_detail(board_id)
    if detail is None:
        # Disabled or unknown provider — still return stored meta.
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
            "document": stored.get("rendered_document") or {"schema_version": 1, "screen": {"type": "vstack", "id": "root", "children": []}},
            "rendered_at": stored.get("rendered_at"),
        }
    return detail


async def delete_board(board_id: str) -> bool:
    await repository.ensure_boards_schema()
    return await repository.delete_board_row(board_id)
