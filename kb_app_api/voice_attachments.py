from __future__ import annotations

import logging
import uuid
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)


def voice_upload_path(session_id: int, safe_filename: str) -> Path:
    kb_root = Path(config.LOCAL_KB_PATH)
    kb_root.mkdir(parents=True, exist_ok=True)
    upload_root = kb_root / ".kb_app_api_uploads" / str(session_id)
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root / f"{uuid.uuid4().hex[:10]}_{safe_filename}"


async def attach_voice_to_last_user_message(
    session_id: int,
    dest: Path,
    safe_filename: str,
    file_size: int,
    transcription: str,
) -> None:
    """Link saved audio file + transcription to the latest user message in the session."""
    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(session_id)
    last_user = None
    for msg in reversed(all_msgs):
        if msg.get("role") == "user":
            last_user = msg
            break
    if not last_user:
        logger.warning("KB App API: нет user-сообщения для voice attachment (session %s)", session_id)
        return

    try:
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=last_user["id"],
            file_type="voice",
            file_id=f"kb_app_api:{uuid.uuid4().hex}",
            file_path=str(dest),
            file_name=safe_filename,
            file_size=file_size,
        )
        await db.add_transcription(
            attachment_id=int(attachment["id"]),
            text=transcription,
            language=None,
        )
    except Exception as e:
        logger.warning("Не удалось сохранить голосовое вложение: %s", e)
