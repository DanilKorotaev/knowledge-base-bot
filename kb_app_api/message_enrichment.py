from __future__ import annotations

import logging
import re
from typing import Any

from kb_app_api.serializers import messages_to_kb

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<\s*(/?)\s*(b|strong|i|em|code|pre|ul|ol|li|a|p|br|blockquote)\b", re.I)


async def enrich_session_messages(session_id: int, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Load attachments + transcriptions and serialize messages for KB App API."""
    if not messages:
        return []

    from utils.db_helpers import get_db

    db = await get_db()
    attachments = await db.get_session_attachments(session_id)
    by_msg: dict[int, list[dict[str, Any]]] = {}
    for att in attachments:
        msg_id = att.get("message_id")
        if msg_id is None:
            continue
        by_msg.setdefault(int(msg_id), []).append(att)

    transcription_by_att: dict[int, str] = {}
    for att in attachments:
        if att.get("file_type") != "voice":
            continue
        att_id = int(att["id"])
        try:
            tr = await db.get_transcription(att_id)
        except Exception as e:
            logger.warning("Не удалось загрузить транскрипцию для attachment %s: %s", att_id, e)
            continue
        if tr and tr.get("text"):
            transcription_by_att[att_id] = str(tr["text"])

    return messages_to_kb(session_id, messages, by_msg, transcription_by_att)
