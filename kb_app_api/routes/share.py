"""Public read-only shared chat links (no Bearer — token in path is the credential)."""
from __future__ import annotations

import hashlib
import html
from typing import Any, Optional

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from kb_app_api.errors import APIError
from kb_app_api.message_enrichment import enrich_session_messages
from kb_app_api.serializers import session_to_kb_from_row
from utils.constants import SessionStatus

router = APIRouter(tags=["share"])


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _strip_private_attachment_urls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """MVP: hide auth-only download_url until share-scoped file URLs exist."""
    cleaned: list[dict[str, Any]] = []
    for message in messages:
        item = dict(message)
        attachments = item.get("attachments")
        if isinstance(attachments, list):
            public_atts: list[dict[str, Any]] = []
            for att in attachments:
                if not isinstance(att, dict):
                    continue
                row = dict(att)
                row.pop("download_url", None)
                public_atts.append(row)
            item["attachments"] = public_atts
        cleaned.append(item)
    return cleaned


async def _load_shared_payload(
    raw_token: str,
    *,
    limit: int,
    before: Optional[str],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    token = (raw_token or "").strip()
    if not token or len(token) > 200:
        raise APIError("not_found", "Ссылка недействительна", status_code=404)

    db = await get_db()
    share = await db.get_active_share_by_token_hash(_hash_token(token))
    if not share:
        raise APIError("not_found", "Ссылка недействительна или истекла", status_code=404)

    sid = int(share["session_id"])
    session = await db.get_session(sid)
    if not session or str(session.get("status") or "") == str(SessionStatus.DELETED):
        raise APIError("not_found", "Ссылка недействительна", status_code=404)

    before_id: Optional[int] = None
    if before:
        try:
            before_id = int(before)
        except ValueError as exc:
            raise APIError("validation_error", "before должен быть id сообщения", detail="before") from exc

    if limit < 1 or limit > 100:
        raise APIError("validation_error", "limit должен быть 1…100", detail="limit")

    chunk, total, has_more_older = await db.get_session_messages_window(
        sid,
        limit=limit,
        before_id=before_id,
    )
    messages = _strip_private_attachment_urls(await enrich_session_messages(sid, chunk))
    return {
        "session": session_to_kb_from_row(session, total),
        "messages": messages,
        "total": total,
        "has_more_older": has_more_older,
        "expires_at": share.get("expires_at"),
    }


@router.get("/api/share/{token}")
async def get_shared_session_json(
    token: str,
    limit: int = Query(50, ge=1, le=100),
    before: Optional[str] = Query(None),
) -> dict[str, Any]:
    payload = await _load_shared_payload(token, limit=limit, before=before)
    expires = payload.get("expires_at")
    if expires is not None and not isinstance(expires, str):
        from kb_app_api.timefmt import to_iso_z

        payload["expires_at"] = to_iso_z(expires)
    return payload


@router.get("/share/{token}", response_class=HTMLResponse)
async def get_shared_session_html(token: str) -> HTMLResponse:
    """Minimal read-only viewer (foundation for a future web KB App)."""
    try:
        payload = await _load_shared_payload(token, limit=100, before=None)
    except APIError as err:
        status = getattr(err, "status_code", 404) or 404
        title = "Ссылка недоступна"
        body = html.escape(str(getattr(err, "message", None) or "Ссылка недействительна"))
        page = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:2rem;color:#222;background:#f7f7f8}}
.card{{max-width:40rem;margin:auto;background:#fff;border-radius:12px;padding:1.25rem 1.5rem;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
</style></head><body><div class="card"><h1>{title}</h1><p>{body}</p></div></body></html>"""
        return HTMLResponse(page, status_code=status)

    session = payload.get("session") or {}
    title = html.escape(str(session.get("title") or "Чат"))
    messages_html: list[str] = []
    for message in payload.get("messages") or []:
        role = str(message.get("role") or "user")
        role_label = "Ассистент" if role == "assistant" else "Вы"
        content = html.escape(str(message.get("content") or "")).replace("\n", "<br>")
        messages_html.append(
            f'<article class="msg {html.escape(role)}">'
            f'<div class="role">{role_label}</div>'
            f'<div class="content">{content}</div>'
            f"</article>"
        )
    if not messages_html:
        messages_html.append('<p class="empty">Пока нет сообщений.</p>')

    joined = "\n".join(messages_html)
    page = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0;background:#f7f7f8;color:#1c1c1e}}
header{{padding:1rem 1.25rem;background:#fff;border-bottom:1px solid #e5e5ea;position:sticky;top:0}}
header h1{{font-size:1.1rem;margin:0}}
header p{{margin:.35rem 0 0;color:#8e8e93;font-size:.85rem}}
main{{max-width:44rem;margin:0 auto;padding:1rem 1.25rem 2rem;display:flex;flex-direction:column;gap:.75rem}}
.msg{{padding:.85rem 1rem;border-radius:14px;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.05)}}
.msg.assistant{{background:#eef2ff}}
.role{{font-size:.75rem;color:#8e8e93;margin-bottom:.35rem}}
.content{{white-space:pre-wrap;line-height:1.45;word-break:break-word}}
.empty{{color:#8e8e93}}
</style></head>
<body>
<header><h1>{title}</h1><p>Только чтение · Knowledge Base</p></header>
<main>
{joined}
</main>
</body></html>"""
    return HTMLResponse(page)
