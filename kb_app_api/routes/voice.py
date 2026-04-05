from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.session_access import assistant_stub_reply, parse_session_id, require_session_for_user
from kb_app_api.serializers import message_to_kb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["voice"])


@router.post("/voice")
async def voice_query(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    audio: Annotated[UploadFile | None, File(None)] = None,
    session_id: Annotated[str, Form()] = "",
    use_knowledge_base: Annotated[str, Form()] = "true",
    transcription_hint: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """
    Заглушка: принимает multipart, не вызывает Whisper.
    Текст для пайплайна — фиксированная строка или transcription_hint.
    """
    _ = audio  # пока не передаём в ASR
    if not session_id.strip():
        raise APIError("validation_error", "Нужно поле session_id", detail="session_id")

    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    use_kb = str(use_knowledge_base).lower() in ("1", "true", "yes", "on")
    text = (transcription_hint or "").strip() or "[голос] заглушка: распознавание не подключено"

    from utils.db_helpers import get_db

    db = await get_db()
    await db.add_message(sid, "user", text)
    reply = assistant_stub_reply(text, use_kb)
    await db.add_message(sid, "assistant", reply)

    all_msgs = await db.get_session_messages(sid)
    return {
        "messages": [message_to_kb(m) for m in all_msgs],
        "transcription": text,
    }
