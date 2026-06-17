"""
Планирование push после сохранения ответа ассистента (KB App API).
"""
from __future__ import annotations

import asyncio
import logging

from kb_app_api.apns_push_service import send_chat_reply_to_devices

logger = logging.getLogger(__name__)


async def notify_chat_reply_ready(
    *,
    session_id: int,
    message_id: int,
    reply_text: str,
) -> None:
    from utils.db_helpers import get_db

    db = await get_db()
    session = await db.get_session(session_id)
    if not session:
        logger.warning("notify_chat_reply_ready: session %s not found", session_id)
        return

    user_id = int(session["user_id"])
    devices = await db.list_user_devices(user_id)
    if not devices:
        return

    title = session.get("display_title") or f"Session {session_id}"
    await send_chat_reply_to_devices(
        devices=devices,
        session_id=session_id,
        message_id=message_id,
        session_title=str(title),
        reply_text=reply_text,
    )


def schedule_chat_reply_push(
    *,
    session_id: int,
    message_id: int,
    reply_text: str,
) -> None:
    """Fire-and-forget из process_query_for_api (не блокирует ответ API)."""

    async def _run() -> None:
        try:
            await notify_chat_reply_ready(
                session_id=session_id,
                message_id=message_id,
                reply_text=reply_text,
            )
        except Exception as e:
            logger.warning("chat reply push failed session=%s: %s", session_id, e)

    asyncio.create_task(_run())
