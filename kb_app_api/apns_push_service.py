"""
Отправка alert push через APNs HTTP/2 API (JWT + .p8 Auth Key).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from config import config

logger = logging.getLogger(__name__)

SANDBOX_URL = "https://api.sandbox.push.apple.com"
PRODUCTION_URL = "https://api.push.apple.com"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def apns_configured() -> bool:
    return bool(
        config.APNS_KEY_ID
        and config.APNS_TEAM_ID
        and config.APNS_AUTH_KEY_PATH
        and config.APNS_TOPIC
        and Path(config.APNS_AUTH_KEY_PATH).is_file()
    )


def preview_plain_text(text: str, limit: int = 100) -> str:
    """Превью ответа для alert body (plain text, без разметки)."""
    plain = _HTML_TAG_RE.sub("", text or "")
    plain = _WHITESPACE_RE.sub(" ", plain).strip()
    if len(plain) <= limit:
        return plain or "Ответ готов"
    return plain[: limit - 1].rstrip() + "…"


def build_chat_reply_payload(
    *,
    session_id: int,
    message_id: int,
    title: str,
    body_preview: str,
) -> dict[str, Any]:
    return {
        "aps": {
            "alert": {"title": title, "body": body_preview},
            "sound": "default",
            "thread-id": str(session_id),
        },
        "type": "chat_reply_ready",
        "session_id": str(session_id),
        "message_id": str(message_id),
    }


def _make_jwt() -> str:
    key_path = Path(config.APNS_AUTH_KEY_PATH or "")
    if not key_path.is_file():
        raise ValueError(f"APNS auth key not found: {key_path}")
    try:
        key = key_path.read_bytes()
    except OSError as e:
        raise ValueError(f"APNS auth key not readable: {key_path} ({e})") from e
    return jwt.encode(
        {"iss": config.APNS_TEAM_ID, "iat": int(time.time())},
        key,
        algorithm="ES256",
        headers={"kid": config.APNS_KEY_ID},
    )


def _apns_base_url(*, sandbox: bool) -> str:
    return SANDBOX_URL if sandbox else PRODUCTION_URL


async def send_push(
    *,
    device_token: str,
    payload: dict[str, Any],
    sandbox: bool,
) -> tuple[int, str]:
    """Отправить один push. Возвращает (status_code, response_body)."""
    token = device_token.strip()
    url = f"{_apns_base_url(sandbox=sandbox)}/3/device/{token}"
    auth = _make_jwt()
    headers = {
        "authorization": f"bearer {auth}",
        "apns-topic": config.APNS_TOPIC,
        "apns-push-type": "alert",
        "content-type": "application/json",
    }
    async with httpx.AsyncClient(http2=True, timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        return response.status_code, response.text


async def send_chat_reply_to_devices(
    *,
    devices: list[dict[str, Any]],
    session_id: int,
    message_id: int,
    session_title: str,
    reply_text: str,
) -> None:
    if not devices:
        return
    if not apns_configured():
        logger.info("APNs not configured — skip push for session %s", session_id)
        return

    title = (session_title or f"Session {session_id}").strip()[:200]
    body = preview_plain_text(reply_text)
    payload = build_chat_reply_payload(
        session_id=session_id,
        message_id=message_id,
        title=title,
        body_preview=body,
    )

    from utils.db_helpers import get_db

    db = await get_db()
    for device in devices:
        token = str(device.get("device_token") or "").strip()
        if not token:
            continue
        env = str(device.get("apns_environment") or "production").lower()
        sandbox = env == "sandbox"
        try:
            status, body_text = await send_push(
                device_token=token,
                payload=payload,
                sandbox=sandbox,
            )
        except Exception as e:
            logger.warning("APNs send failed for token …%s: %s", token[-8:], e)
            continue

        if status == 200:
            logger.info("APNs push sent session=%s message=%s token=…%s", session_id, message_id, token[-8:])
        elif status == 410:
            logger.info("APNs token expired (410), removing …%s", token[-8:])
            await db.delete_user_device(int(device["user_id"]), token)
        else:
            logger.warning(
                "APNs push failed status=%s session=%s token=…%s body=%s",
                status,
                session_id,
                token[-8:],
                body_text[:500],
            )
