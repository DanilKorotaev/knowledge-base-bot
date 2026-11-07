"""High-level helpers to record inbox rows next to push dispatch."""
from __future__ import annotations

import logging
from typing import Any

from kb_app_api.notifications import store

logger = logging.getLogger(__name__)


async def record_agent_reply(
    *,
    user_id: int,
    session_id: int,
    message_id: int,
    title: str,
    body: str,
) -> dict[str, Any] | None:
    try:
        return await store.create_notification(
            user_id=user_id,
            kind="agent_reply",
            title=(title or f"Session {session_id}")[:200],
            body=(body or "")[:500],
            source_key="agent",
            session_id=session_id,
            message_id=message_id,
            dedupe_key=f"agent_reply:{session_id}:{message_id}",
            payload={"session_id": session_id, "message_id": message_id},
        )
    except Exception:
        logger.exception(
            "record_agent_reply failed user=%s session=%s message=%s",
            user_id,
            session_id,
            message_id,
        )
        return None


async def record_ingress_event(
    *,
    user_id: int,
    session_id: int,
    message_id: int,
    title: str,
    body: str = "",
    source_key: str | None = None,
    event_id: str | None = None,
    participant_label: str | None = None,
) -> dict[str, Any] | None:
    try:
        dedupe = f"ingress:{event_id}" if event_id else f"ingress_msg:{message_id}"
        return await store.create_notification(
            user_id=user_id,
            kind="ingress_event",
            title=(title or "External event")[:200],
            body=(body or "")[:500],
            source_key=source_key,
            session_id=session_id,
            message_id=message_id,
            event_id=event_id,
            dedupe_key=dedupe,
            payload={
                "session_id": session_id,
                "message_id": message_id,
                "event_id": event_id,
                "participant_label": participant_label,
            },
        )
    except Exception:
        logger.exception(
            "record_ingress_event failed user=%s session=%s event=%s",
            user_id,
            session_id,
            event_id,
        )
        return None
