"""Overview / Boards API — list + detail + refresh + upsert/delete (MCP / agent)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from kb_app_api.boards_catalog import delete_board, get_board_detail, list_boards, upsert_board
from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError

router = APIRouter(prefix="/boards", tags=["boards"])


class BoardUpsertBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=400)
    icon: str | None = Field(default=None, max_length=80)
    kind: str = Field(default="cached_view", max_length=40)
    sort_order: int = Field(default=0, ge=0, le=1_000_000)
    enabled: bool = True
    definition: dict[str, Any] = Field(default_factory=dict)
    list_cell: dict[str, Any] | None = None
    rendered_document: dict[str, Any] | None = None
    rendered_at: str | None = None


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
    period: Annotated[str | None, Query(description="YYYY-MM or all")] = None,
    date_from: Annotated[
        str | None, Query(alias="from", description="Inclusive ISO date YYYY-MM-DD")
    ] = None,
    date_to: Annotated[
        str | None, Query(alias="to", description="Inclusive ISO date YYYY-MM-DD")
    ] = None,
) -> dict[str, Any]:
    _ = user
    detail = await get_board_detail(
        board_id, period=period, date_from=date_from, date_to=date_to
    )
    if detail is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return detail


@router.put("/{board_id}")
async def put_board(
    board_id: str,
    body: BoardUpsertBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Create or replace a board definition (used by MCP / agents)."""
    _ = user
    payload = body.model_dump()
    payload["id"] = board_id
    try:
        return await upsert_board(payload)
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc


@router.delete("/{board_id}")
async def remove_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    _ = user
    deleted = await delete_board(board_id)
    if not deleted:
        raise APIError("not_found", "Board not found", status_code=404)
    return {"ok": True, "id": board_id}


@router.post("/{board_id}/refresh")
async def refresh_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    period: Annotated[str | None, Query(description="YYYY-MM or all")] = None,
    date_from: Annotated[
        str | None, Query(alias="from", description="Inclusive ISO date YYYY-MM-DD")
    ] = None,
    date_to: Annotated[
        str | None, Query(alias="to", description="Inclusive ISO date YYYY-MM-DD")
    ] = None,
) -> dict[str, Any]:
    """Recompute live providers (vault read-only) or return static document."""
    _ = user
    detail = await get_board_detail(
        board_id, period=period, date_from=date_from, date_to=date_to
    )
    if detail is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return detail
