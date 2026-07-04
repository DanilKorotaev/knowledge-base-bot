from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from kb_app_api.serializers import messages_to_kb
from kb_app_api.structured_ui.persistence import structured_ui_by_message_ids

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<\s*(/?)\s*(b|strong|i|em|code|pre|ul|ol|li|a|p|br|blockquote)\b", re.I)


def _to_utc_datetime(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    value = str(raw).strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _related_changed_files_by_message(
    messages: list[dict[str, Any]],
    file_changes: list[dict[str, Any]],
) -> tuple[dict[int, list[dict[str, Any]]], dict[int, str]]:
    assistant_messages: list[dict[str, Any]] = [m for m in messages if str(m.get("role") or "") == "assistant"]
    if not assistant_messages or not file_changes:
        return {}, {}

    ordered_changes = sorted(
        file_changes,
        key=lambda item: (_to_utc_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)),
    )
    pointer = 0
    per_message: dict[int, list[dict[str, Any]]] = {}
    per_message_source: dict[int, str] = {}
    previous_assistant_ts: datetime | None = None
    max_related_items = 8

    for message in assistant_messages:
        message_id = int(message["id"])
        message_ts = _to_utc_datetime(message.get("created_at"))
        if message_ts is None:
            continue

        bucket: list[dict[str, Any]] = []
        while pointer < len(ordered_changes):
            change = ordered_changes[pointer]
            change_ts = _to_utc_datetime(change.get("created_at"))
            if change_ts is None:
                pointer += 1
                continue
            if previous_assistant_ts is not None and change_ts <= previous_assistant_ts:
                pointer += 1
                continue
            if change_ts > message_ts:
                break
            bucket.append(change)
            pointer += 1

        if bucket:
            per_message[message_id] = list(reversed(bucket[-max_related_items:]))
            per_message_source[message_id] = "reply"
        previous_assistant_ts = message_ts

    latest_assistant_id = int(assistant_messages[-1]["id"])
    if latest_assistant_id not in per_message:
        recent = sorted(
            file_changes,
            key=lambda item: (
                _to_utc_datetime(item.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )[:5]
        if recent:
            per_message[latest_assistant_id] = recent
            per_message_source[latest_assistant_id] = "recent"

    return per_message, per_message_source


async def enrich_session_messages(session_id: int, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Load attachments + transcriptions and serialize messages for KB App API."""
    if not messages:
        return []

    from utils.db_helpers import get_db

    db = await get_db()
    attachments = await db.get_session_attachments(session_id)
    file_changes = await db.get_file_changes(session_id=session_id)
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

    related_changed_files_by_msg, changed_files_source_by_msg = _related_changed_files_by_message(messages, file_changes)
    structured_ui_by_msg = structured_ui_by_message_ids(messages)
    return messages_to_kb(
        session_id,
        messages,
        by_msg,
        transcription_by_att,
        related_changed_files_by_msg,
        changed_files_source_by_msg,
        structured_ui_by_msg,
    )
