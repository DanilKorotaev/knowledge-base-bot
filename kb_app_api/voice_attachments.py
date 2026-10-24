from __future__ import annotations

import logging
import uuid
from pathlib import Path

from kb_app_api.vault_paths import resolve_kb_root

logger = logging.getLogger(__name__)


def voice_upload_path(
    session_id: int,
    safe_filename: str,
    *,
    user: dict | None = None,
    kb_root: Path | None = None,
) -> Path:
    root = Path(kb_root) if kb_root is not None else resolve_kb_root(user)
    root.mkdir(parents=True, exist_ok=True)
    upload_root = root / ".kb_app_api_uploads" / str(session_id)
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root / f"{uuid.uuid4().hex[:10]}_{safe_filename}"


async def attach_voice_to_message(
    session_id: int,
    message_id: int,
    dest: Path,
    safe_filename: str,
    file_size: int,
    transcription: str,
) -> None:
    """Link saved audio file + transcription to an explicit user message."""
    from utils.db_helpers import get_db

    db = await get_db()
    try:
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=message_id,
            file_type="voice",
            file_id=f"kb_app_api:{uuid.uuid4().hex}",
            file_path=str(dest),
            file_name=safe_filename,
            file_size=file_size,
        )
        if transcription.strip():
            await db.add_transcription(
                attachment_id=int(attachment["id"]),
                text=transcription.strip(),
                language=None,
            )
    except Exception as e:
        logger.warning("Не удалось сохранить голосовое вложение: %s", e)


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

    await attach_voice_to_message(
        session_id,
        int(last_user["id"]),
        dest,
        safe_filename,
        file_size,
        transcription,
    )
