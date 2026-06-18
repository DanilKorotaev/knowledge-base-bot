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
        logger.info(
            "chat reply push skipped session=%s message=%s: no registered devices",
            session_id,
            message_id,
        )
        return

    title = session.get("display_title") or f"Session {session_id}"
    logger.info(
        "chat reply push sending session=%s message=%s devices=%s",
        session_id,
        message_id,
        len(devices),
    )
    await send_chat_reply_to_devices(
        devices=devices,
        session_id=session_id,
        message_id=message_id,
        session_title=str(title),
        reply_text=reply_text,
    )


_PUSH_TIMEOUT_SEC = float(__import__("os").getenv("APNS_PUSH_TIMEOUT_SEC", "25"))


async def deliver_chat_reply_push(
    *,
    session_id: int,
    message_id: int,
    reply_text: str,
) -> None:
    """Отправить push с таймаутом; ошибки логируем, pipeline не роняем."""
    try:
        await asyncio.wait_for(
            notify_chat_reply_ready(
                session_id=session_id,
                message_id=message_id,
                reply_text=reply_text,
            ),
            timeout=_PUSH_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "chat reply push timed out after %.0fs session=%s message=%s",
            _PUSH_TIMEOUT_SEC,
            session_id,
            message_id,
        )
    except Exception as e:
        logger.warning("chat reply push failed session=%s message=%s: %s", session_id, message_id, e)


def schedule_chat_reply_push(
    *,
    session_id: int,
    message_id: int,
    reply_text: str,
) -> None:
    """Fire-and-forget (legacy). Prefer ``await deliver_chat_reply_push`` in pipelines."""

    async def _run() -> None:
        await deliver_chat_reply_push(
            session_id=session_id,
            message_id=message_id,
            reply_text=reply_text,
        )

    asyncio.create_task(_run())
