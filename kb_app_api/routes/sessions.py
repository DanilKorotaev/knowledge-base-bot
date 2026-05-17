from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.serializers import session_to_kb
from utils.constants import SessionType, SessionStatus

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionBody(BaseModel):
    title: str = Field(default="Новый чат", max_length=500)


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
    raw = await db.get_user_sessions(user["id"], limit=500, status=None)
    sessions = [s for s in raw if s.get("status") != "deleted"]

    start = (page - 1) * per_page
    slice_ = sessions[start : start + per_page]

    items: list[dict[str, Any]] = []
    for s in slice_:
        messages = await db.get_session_messages(s["id"])
        items.append(session_to_kb(s, messages))

    return {"sessions": items, "total": len(sessions), "page": page, "per_page": per_page}


@router.get("/search")
async def search_sessions(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    q: str = Query(..., min_length=1, description="ID сессии или текст из сообщений"),
) -> dict[str, Any]:
    """Поиск по ID сессии или содержимому сообщений (как в Mini App)."""
    from utils.db_helpers import get_db

    db = await get_db()
    raw = await db.get_user_sessions(user["id"], limit=500, status=None)
    sessions = [s for s in raw if s.get("status") != "deleted"]

    query = q.strip()
    try:
        search_id = int(query.lstrip("#"))
        id_matches = [s for s in sessions if s["id"] == search_id]
        if id_matches:
            items = []
            for s in id_matches:
                messages = await db.get_session_messages(s["id"])
                items.append(session_to_kb(s, messages))
            return {"sessions": items, "total": len(items)}
    except ValueError:
        pass

    q_lower = query.lower()
    matching: list[dict[str, Any]] = []
    for session in sessions:
        title = (session.get("display_title") or f"Session {session['id']}").lower()
        if q_lower in title:
            messages = await db.get_session_messages(session["id"])
            matching.append(session_to_kb(session, messages))
            continue
        messages = await db.get_session_messages(session["id"])
        for msg in messages:
            if q_lower in (msg.get("content") or "").lower():
                matching.append(session_to_kb(session, messages))
                break

    return {"sessions": matching, "total": len(matching)}


@router.post("", status_code=201)
async def create_session(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: CreateSessionBody,
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    session = await db.create_session(
        user_id=user["id"],
        session_type=str(SessionType.QUERY_WITH_KB),
        status=str(SessionStatus.ACTIVE),
        context_files=None,
        display_title=body.title.strip() or None,
    )
    messages = await db.get_session_messages(session["id"])
    return {"session": session_to_kb(session, messages)}
