"""Post a follow-up when the log file arrives after the crash report."""
from __future__ import annotations

import logging
from typing import Any

from utils.constants import MessageRole
from utils.db_helpers import get_db

from kb_app_api.ingress.deliver import _enqueue_untrusted_job, _set_message_metadata

logger = logging.getLogger(__name__)


async def deliver_log_followup(
    *,
    user_id: int,
    log_session: str,
    chat_session_id: int,
    app_version: str,
    app_build: str,
) -> dict[str, Any] | None:
    summary = f"KB iOS log {app_version} ({app_build}) session {log_session}"
    detail = (
        "The full log file for this crash is available to an admin by log_session. "
        "The app version is the code snapshot where the process crashed. "
        "The defect may have been introduced in an earlier version."
    )
    hints = {
        "log_session": log_session,
        "app_version": app_version,
        "app_build": app_build,
        "logs_status": "ready",
        "code_state_note": "version is a snapshot, not the introducing commit",
    }
    db = await get_db()
    try:
        message = await db.add_message(
            int(chat_session_id),
            str(MessageRole.EXTERNAL),
            summary,
            client_message_id=f"crash-log:{user_id}:{log_session}",
        )
    except Exception:
        logger.exception("crash log follow-up message failed session=%s", log_session)
        return None
    await _set_message_metadata(
        int(message["id"]),
        {
            "summary": summary,
            "detail": detail,
            "participant": {"key": "ios", "label": "ios", "avatar_url": None},
            "source": "ios",
            "type": "app.crash_logs",
            "links": [],
            "event_id": f"crash-log:{log_session}",
            "hints": hints,
        },
    )
    job_id = await _enqueue_untrusted_job(
        user_id=user_id,
        session_id=int(chat_session_id),
        summary=summary,
        event_id=f"crash-log:{log_session}",
        agent_prompt_profile="untrusted_ingress",
        agent_runtime="host",
    )
    return {"message_id": message["id"], "job_id": job_id}
