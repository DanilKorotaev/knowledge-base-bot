from __future__ import annotations

from typing import Any

from kb_app_api.timefmt import to_iso_z


def message_to_kb(m: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(m["id"]),
        "role": m["role"],
        "content": m["content"],
        "created_at": to_iso_z(m["created_at"]),
    }


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
