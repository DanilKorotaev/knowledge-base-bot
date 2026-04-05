from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.revert_helpers import revert_file_change_or_raise
from kb_app_api.timefmt import to_iso_z

router = APIRouter(prefix="/files", tags=["files"])


def _change_kind(db_type: str) -> str:
    m = (db_type or "").lower()
    if m in ("created", "modified", "deleted"):
        return m
    return "modified"


@router.get("/changes")
async def list_file_changes(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    session_id: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    sid: int | None = None
    if session_id is not None and session_id.strip():
        try:
            sid = int(session_id)
        except ValueError:
            raise APIError("validation_error", "Некорректный session_id", detail=session_id)
        sess = await db.get_session(sid)
        if not sess or sess["user_id"] != user["id"]:
            raise APIError("forbidden", "Нет доступа к этой сессии", status_code=403)

    rows = await db.get_file_changes(session_id=sid)
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r["id"]),
                "path": r["file_path"],
                "change_kind": _change_kind(r.get("change_type", "")),
                "before_text": r.get("old_content"),
                "after_text": r.get("new_content"),
                "created_at": to_iso_z(r.get("created_at")),
            }
        )
    return {"items": items}


class RevertBody(BaseModel):
    file_id: str = Field(..., description="Идентификатор записи изменения (как в GET /changes)")


@router.post("/revert")
async def revert_file(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: RevertBody,
) -> dict[str, Any]:
    raw = body.file_id.strip()
    if not raw:
        raise APIError("validation_error", "Пустой file_id", detail="file_id")
    try:
        change_id = int(raw)
    except ValueError:
        raise APIError("validation_error", "file_id должен быть числом", detail=body.file_id)

    return await revert_file_change_or_raise(change_id, user["id"])
