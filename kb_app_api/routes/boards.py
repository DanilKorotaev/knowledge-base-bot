"""Overview / Boards API — list + detail + refresh + upsert/delete (MCP / agent)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from kb_app_api.boards_catalog import (
    archive_board,
    delete_board,
    get_board_detail,
    list_archived_boards,
    list_boards,
    reorder_boards,
    restore_board,
    upsert_board,
)
from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError

router = APIRouter(prefix="/boards", tags=["boards"])


class BoardUpsertBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=400)
    icon: str | None = Field(default=None, max_length=80)
    kind: str = Field(default="cached_view", max_length=40)
    # None = append on create / keep existing on update
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)
    enabled: bool = True
    definition: dict[str, Any] = Field(default_factory=dict)
    list_cell: dict[str, Any] | None = None
    rendered_document: dict[str, Any] | None = None
    rendered_at: str | None = None


class BoardReorderBody(BaseModel):
    ordered_ids: list[str] = Field(..., min_length=1, max_length=200)


@router.get("")
async def get_boards(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    boards = await list_boards(user_id=int(user["id"]))
    return {"boards": boards, "total": len(boards)}


@router.put("/order")
async def put_boards_order(
    body: BoardReorderBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Persist Overview tab order (drag-and-drop). ``ordered_ids`` = enabled boards."""
    _ = user
    try:
        boards = await reorder_boards(body.ordered_ids)
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc
    return {"boards": boards, "total": len(boards)}


@router.get("/archived")
async def get_archived_boards(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Boards hidden from Overview (``enabled=false``)."""
    _ = user
    boards = await list_archived_boards()
    return {"boards": boards, "total": len(boards)}


@router.post("/{board_id}/archive")
async def post_archive_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Hide board from Overview without deleting its definition."""
    _ = user
    try:
        board = await archive_board(board_id)
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc
    if board is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return {"ok": True, "board": board}


@router.post("/{board_id}/restore")
async def post_restore_board(
    board_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Return an archived board to Overview (appended at end)."""
    _ = user
    try:
        board = await restore_board(board_id)
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc
    if board is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return {"ok": True, "board": board}


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
    detail = await get_board_detail(
        board_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=int(user["id"]),
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
    detail = await get_board_detail(
        board_id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        user_id=int(user["id"]),
    )
    if detail is None:
        raise APIError("not_found", "Board not found", status_code=404)
    return detail
