"""Boards catalog API surface — DB-backed definitions + provider runtime."""
from __future__ import annotations

import re
from pathlib import Path
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
    kb_root: Path | None = None,
) -> list[dict[str, Any]]:
    return await runtime.list_boards(
        include_disabled=include_disabled,
        user_id=user_id,
        kb_root=kb_root,
    )


async def get_board_detail(
    board_id: str,
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    user_id: int | None = None,
    kb_root: Path | None = None,
) -> dict[str, Any] | None:
    return await runtime.get_board_detail(
        board_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        kb_root=kb_root,
    )


async def upsert_board(
    payload: dict[str, Any],
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Create or replace a board definition, then return rendered detail."""
    board_id = validate_board_id(str(payload.get("id") or ""))
    await repository.ensure_boards_schema()
    if user_id is None:
        raise ValueError("user_id is required to upsert a board")
    existing = await repository.get_board_row(board_id, user_id=user_id)

    raw_sort = payload.get("sort_order")
    if existing is None:
        # New boards append to the end unless an explicit positive order is given.
        if raw_sort is None or int(raw_sort or 0) <= 0:
            sort_order = await repository.next_sort_order(user_id=user_id)
        else:
            sort_order = int(raw_sort)
    elif raw_sort is None:
        sort_order = int(existing.get("sort_order") or 0)
    else:
        sort_order = int(raw_sort)

    row = {
        "id": board_id,
        "user_id": user_id if user_id is not None else (existing or {}).get("user_id"),
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
    detail = await runtime.get_board_detail(board_id, user_id=user_id)
    if detail is None:
        stored = await repository.get_board_row(board_id, user_id=user_id)
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


async def reorder_boards(
    ordered_ids: list[str],
    *,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Persist Overview list order; returns refreshed board list."""
    await repository.set_board_sort_orders(ordered_ids, user_id=user_id)
    return await runtime.list_boards(include_disabled=False, user_id=user_id)


async def list_archived_boards(*, user_id: int | None = None) -> list[dict[str, Any]]:
    """Boards with ``enabled=false`` — metadata + last ``list_cell`` (no recompute)."""
    return await runtime.list_archived_boards(user_id=user_id)


async def archive_board(
    board_id: str,
    *,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    """Hide board from Overview (``enabled=false``). Keeps definition."""
    board_id = validate_board_id(board_id)
    if await repository.get_board_row(board_id, user_id=user_id) is None:
        return None
    row = await repository.set_board_enabled(board_id, enabled=False, user_id=user_id)
    if row is None:
        return None
    return runtime.public_board_from_row(row)


async def restore_board(
    board_id: str,
    *,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    """Bring board back to Overview at the end of the list."""
    board_id = validate_board_id(board_id)
    existing = await repository.get_board_row(board_id, user_id=user_id)
    if existing is None:
        return None
    sort_order = await repository.next_sort_order(user_id=user_id)
    row = await repository.set_board_enabled(
        board_id, enabled=True, sort_order=sort_order, user_id=user_id
    )
    if row is None:
        return None
    return runtime.public_board_from_row(row)


async def delete_board(board_id: str, *, user_id: int | None = None) -> bool:
    await repository.ensure_boards_schema()
    if await repository.get_board_row(board_id, user_id=user_id) is None:
        return False
    return await repository.delete_board_row(board_id, user_id=user_id)


async def list_presets_for_user(*, user_id: int) -> list[dict[str, Any]]:
    from kb_app_api.boards.presets import list_preset_catalog

    await repository.ensure_boards_schema()
    installed = {
        str(b["id"])
        for b in await repository.list_board_rows(include_disabled=True, user_id=user_id)
    }
    out: list[dict[str, Any]] = []
    for preset in list_preset_catalog():
        item = dict(preset)
        item["installed"] = preset["id"] in installed
        out.append(item)
    return out


async def install_preset(*, user_id: int, preset_id: str) -> dict[str, Any]:
    from kb_app_api.boards.presets import get_preset, preset_to_board_row

    preset = get_preset(preset_id)
    if preset is None:
        raise ValueError(f"unknown preset: {preset_id}")
    await repository.ensure_boards_schema()
    existing = await repository.get_board_row(preset["id"], user_id=user_id)
    if existing is not None:
        return await get_board_detail(preset["id"], user_id=user_id) or {
            "board": runtime.public_board_from_row(existing)
        }
    row = preset_to_board_row(preset, user_id=user_id)
    if int(row.get("sort_order") or 0) <= 0:
        row["sort_order"] = await repository.next_sort_order(user_id=user_id)
    await repository.upsert_board_row(row)
    detail = await get_board_detail(preset["id"], user_id=user_id)
    if detail is None:
        stored = await repository.get_board_row(preset["id"], user_id=user_id)
        assert stored is not None
        return {"board": runtime.public_board_from_row(stored)}
    return detail


async def uninstall_preset(*, user_id: int, preset_id: str) -> bool:
    from kb_app_api.boards.presets import get_preset

    if get_preset(preset_id) is None:
        raise ValueError(f"unknown preset: {preset_id}")
    return await delete_board(preset_id, user_id=user_id)
