from __future__ import annotations

from typing import Any

from kb_app_api.errors import APIError


def parse_session_id(session_id: str) -> int:
    try:
        sid = int(session_id)
        if sid < 1:
            raise ValueError
        return sid
    except (TypeError, ValueError):
        raise APIError("validation_error", "Некорректный session_id", detail=session_id)


async def require_session_for_user(session_id: int, user_internal_id: int) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    session = await db.get_session(session_id)
    if not session:
        raise APIError("not_found", "Сессия не найдена", status_code=404)
    if session["user_id"] != user_internal_id:
        raise APIError("forbidden", "Нет доступа к этой сессии", status_code=403)
    if session.get("status") == "deleted":
        raise APIError("not_found", "Сессия удалена", status_code=404)
    return session


def assistant_stub_reply(content: str, use_kb: bool) -> str:
    if use_kb:
        return (
            "[заглушка] Ответ через базу знаний пока не подключён к HTTP API. "
            f"Ваш текст ({len(content)} симв.) сохранён."
        )
    return f"[заглушка] echo: {content[:2000]}"
