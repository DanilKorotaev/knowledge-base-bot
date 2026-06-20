from __future__ import annotations

import mimetypes
import re
from typing import Any

from kb_app_api.timefmt import to_iso_z

_HTML_TAG_RE = re.compile(r"<\s*(/?)\s*(b|strong|i|em|code|pre|ul|ol|li|a|p|br|blockquote)\b", re.I)

_ATTACHMENT_MIME: dict[str, str] = {
    "photo": "image/jpeg",
    "voice": "audio/ogg",
    "audio": "audio/mpeg",
    "video": "video/mp4",
    "document": "application/octet-stream",
}


def infer_content_format(role: str, content: str) -> str:
    """markdown for assistant (Cursor default), plain for user/system; html if content looks like HTML."""
    if role == "assistant" and content and _HTML_TAG_RE.search(content):
        return "html"
    if role == "assistant":
        return "markdown"
    return "plain"


def _guess_mime(att: dict[str, Any]) -> str | None:
    name = att.get("file_name") or ""
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        return guessed
    ftype = att.get("file_type") or ""
    return _ATTACHMENT_MIME.get(str(ftype))


def attachment_to_kb(
    session_id: int,
    att: dict[str, Any],
    transcription_by_att: dict[int, str],
) -> dict[str, Any]:
    att_id = int(att["id"])
    payload: dict[str, Any] = {
        "id": str(att_id),
        "file_type": att.get("file_type") or "document",
        "file_name": att.get("file_name"),
        "file_size": att.get("file_size"),
        "download_url": f"/api/sessions/{session_id}/attachments/{att_id}/file",
    }
    mime = _guess_mime(att)
    if mime:
        payload["mime_type"] = mime
    if att.get("file_type") == "voice":
        tr = transcription_by_att.get(att_id)
        if tr:
            payload["transcription"] = tr
    return payload


def changed_file_to_kb(row: dict[str, Any]) -> dict[str, Any]:
    change_kind = str(row.get("change_type") or "").lower()
    if change_kind not in ("created", "modified", "deleted"):
        change_kind = "modified"
    return {
        "id": str(row["id"]),
        "path": row.get("file_path") or "",
        "change_kind": change_kind,
        "before_text": row.get("old_content"),
        "after_text": row.get("new_content"),
        "created_at": to_iso_z(row.get("created_at")),
    }


def message_to_kb(
    session_id: int,
    m: dict[str, Any],
    attachments: list[dict[str, Any]] | None = None,
    transcription_by_att: dict[int, str] | None = None,
    related_changed_files: list[dict[str, Any]] | None = None,
    changed_files_source: str | None = None,
) -> dict[str, Any]:
    transcription_by_att = transcription_by_att or {}
    role = str(m.get("role") or "user")
    content = m.get("content") or ""
    payload: dict[str, Any] = {
        "id": str(m["id"]),
        "role": role,
        "content": content,
        "content_format": infer_content_format(role, content),
        "created_at": to_iso_z(m["created_at"]),
    }
    if attachments:
        kb_atts = [attachment_to_kb(session_id, a, transcription_by_att) for a in attachments]
        payload["attachments"] = kb_atts
        voice_tr = next(
            (a.get("transcription") for a in kb_atts if a.get("file_type") == "voice" and a.get("transcription")),
            None,
        )
        if voice_tr:
            payload["transcription"] = voice_tr
    if related_changed_files:
        payload["related_changed_files"] = [changed_file_to_kb(item) for item in related_changed_files]
        payload["related_changed_files_source"] = changed_files_source or "reply"
    return payload


def messages_to_kb(
    session_id: int,
    messages: list[dict[str, Any]],
    attachments_by_msg: dict[int, list[dict[str, Any]]],
    transcription_by_att: dict[int, str],
    related_changed_files_by_msg: dict[int, list[dict[str, Any]]] | None = None,
    changed_files_source_by_msg: dict[int, str] | None = None,
) -> list[dict[str, Any]]:
    related_changed_files_by_msg = related_changed_files_by_msg or {}
    changed_files_source_by_msg = changed_files_source_by_msg or {}
    out: list[dict[str, Any]] = []
    for m in messages:
        msg_id = int(m["id"])
        atts = attachments_by_msg.get(msg_id, [])
        out.append(
            message_to_kb(
                session_id,
                m,
                attachments=atts if atts else None,
                transcription_by_att=transcription_by_att,
                related_changed_files=related_changed_files_by_msg.get(msg_id),
                changed_files_source=changed_files_source_by_msg.get(msg_id),
            )
        )
    return out


def session_to_kb(session: dict[str, Any], messages: list[dict[str, Any]]) -> dict[str, Any]:
    title = session.get("display_title") or f"Session {session['id']}"
    if messages:
        last_ts = max(m["created_at"] for m in messages)
    else:
        last_ts = session.get("updated_at") or session.get("created_at")
    return {
        "id": str(session["id"]),
        "title": title,
        "message_count": len(messages),
        "updated_at": to_iso_z(last_ts),
    }
