"""Overview / Boards API — list + detail + refresh (DB definitions + providers)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from kb_app_api.boards_catalog import get_board_detail, list_boards
from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("")
async def get_boards(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    _ = user
    boards = await list_boards()
    return {"boards": boards, "total": len(boards)}


@router.get("/{board_id}")
async def get_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    _ = user
    detail = await get_board_detail(board_id)
    if detail is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return detail


@router.post("/{board_id}/refresh")
async def refresh_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Recompute live providers (vault read-only) or return static document."""
    _ = user
    detail = await get_board_detail(board_id)
    if detail is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return detail
