from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.serializers import session_to_kb_from_row
from kb_app_api.session_access import parse_session_id, require_session_for_user
from utils.constants import SessionStatus, SessionType

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionBody(BaseModel):
    title: str = Field(default="Новый чат", max_length=500)
    use_knowledge_base: bool = True


class PatchSessionBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)


@router.get("")
async def list_sessions(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    page: int = 1,
    per_page: int = 20,
) -> dict[str, Any]:
    if page < 1:
        raise APIError("validation_error", "page должен быть >= 1", detail="page")
    if per_page < 1 or per_page > 100:
        raise APIError("validation_error", "per_page должен быть 1…100", detail="per_page")

    from utils.db_helpers import get_db

    db = await get_db()
    total = await db.count_user_sessions(user["id"], exclude_deleted=True)
    offset = (page - 1) * per_page
    rows = await db.get_user_sessions_with_counts(
        user["id"],
        limit=per_page,
        offset=offset,
        exclude_deleted=True,
    )
    items = [session_to_kb_from_row(s, int(s.get("message_count") or 0)) for s in rows]
    return {"sessions": items, "total": total, "page": page, "per_page": per_page}


@router.get("/search")
async def search_sessions(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    q: str = Query(..., min_length=1, description="ID сессии или текст из сообщений"),
) -> dict[str, Any]:
    """Поиск по ID сессии или содержимому сообщений (как в Mini App)."""
    from utils.db_helpers import get_db

    db = await get_db()
    rows = await db.search_user_sessions_with_counts(user["id"], q, limit=100)
    items = [session_to_kb_from_row(s, int(s.get("message_count") or 0)) for s in rows]
    return {"sessions": items, "total": len(items)}


@router.post("", status_code=201)
async def create_session(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: CreateSessionBody,
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    session_type = (
        SessionType.QUERY_WITH_KB if body.use_knowledge_base else SessionType.EMPTY_CHAT
    )
    session = await db.create_session(
        user_id=user["id"],
        session_type=str(session_type),
        status=str(SessionStatus.ACTIVE),
        context_files=None,
        display_title=body.title.strip() or None,
    )
    return {"session": session_to_kb_from_row(session, 0)}


@router.patch("/{session_id}")
async def patch_session(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: PatchSessionBody,
) -> dict[str, Any]:
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    title = body.title.strip()
    if not title:
        raise APIError("validation_error", "title не может быть пустым", detail="title")

    from utils.db_helpers import get_db

    db = await get_db()
    await db.update_session(sid, display_title=title)
    session = await db.get_session(sid)
    if not session:
        raise APIError("not_found", "Сессия не найдена", status_code=404)
    count = await db.count_session_messages(sid)
    return {"session": session_to_kb_from_row(session, count)}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    from utils.db_helpers import get_db

    db = await get_db()
    await db.update_session(sid, status=str(SessionStatus.DELETED))
    return {"success": True}
