"""Boards catalog API surface — DB-backed definitions + provider runtime."""
from __future__ import annotations

from typing import Any

from kb_app_api.boards import runtime


async def list_boards(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    return await runtime.list_boards(include_disabled=include_disabled)


async def get_board_detail(board_id: str) -> dict[str, Any] | None:
    return await runtime.get_board_detail(board_id)
