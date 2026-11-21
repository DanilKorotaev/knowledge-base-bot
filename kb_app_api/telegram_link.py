"""One-time codes that bind a Telegram account to an existing KB App user."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from kb_app_api.errors import APIError

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_LINK_TTL = timedelta(minutes=20)
_INVITE_TTL = timedelta(days=7)


def _new_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


LINK_REQUIRED = (
    "Telegram не привязан к аккаунту базы знаний. "
    "В приложении получите код и отправьте боту /link КОД."
)


def telegram_linked(user: dict[str, Any]) -> bool:
    tid = user.get("telegram_id")
    if tid is None:
        return False
    try:
        return int(tid) > 0
    except (TypeError, ValueError):
        return False


def link_payload(code: str, *, purpose: str, expires_at: str) -> dict[str, Any]:
    return {
        "code": code,
        "command": f"/link {code}",
        "purpose": purpose,
        "expires_at": expires_at,
    }


async def issue_link_code(db: Any, user_id: int, *, purpose: str = "link") -> dict[str, Any]:
    if purpose not in ("link", "invite"):
        raise APIError("validation_error", "purpose должен быть link или invite", detail="purpose")
    code = _new_code()
    ttl = _LINK_TTL if purpose == "link" else _INVITE_TTL
    expires = _iso(_now() + ttl)
    await db.insert_telegram_link_token(code, int(user_id), purpose, expires)
    return link_payload(code, purpose=purpose, expires_at=expires)


async def _load_open_token(db: Any, code: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    token = (code or "").strip().upper()
    if not token:
        raise APIError("validation_error", "Нужен код привязки", detail="code")
    row = await db.get_telegram_link_token(token)
    if not row or row.get("used_at"):
        raise APIError("not_found", "Код не найден или уже использован", status_code=404)
    if _parse_iso(row["expires_at"]) <= _now():
        raise APIError("expired", "Срок кода истёк", status_code=410)
    user = await db.get_user_by_id(int(row["user_id"]))
    if not user or not user.get("login"):
        raise APIError("not_found", "Аккаунт для этого кода не найден", status_code=404)
    return token, row, user


async def preview_link_code(db: Any, code: str, telegram_id: int) -> dict[str, Any]:
    """What a confirm screen should say. Does not bind and does not spend the code."""
    token, row, user = await _load_open_token(db, code)
    telegram_id = int(telegram_id)
    holder = await db.get_user_by_telegram_id(telegram_id)
    holder_login = None
    if (
        holder
        and holder.get("login")
        and telegram_linked(holder)
        and int(holder["id"]) != int(user["id"])
    ):
        holder_login = str(holder["login"])

    current = user.get("telegram_id")
    same = (
        current is not None
        and int(current) > 0
        and int(current) == telegram_id
    )
    account_taken = (
        current is not None
        and int(current) > 0
        and int(current) != telegram_id
    )
    if same:
        status = "same"
    elif holder_login:
        status = "telegram_taken"
    elif account_taken:
        status = "account_taken"
    else:
        status = "ready"
    return {
        "code": token,
        "login": user["login"],
        "purpose": row.get("purpose") or "link",
        "status": status,
        "holder_login": holder_login,
    }


async def accept_link_code(
    db: Any,
    code: str,
    telegram_id: int,
    username: str | None = None,
) -> dict[str, Any]:
    token, _row, user = await _load_open_token(db, code)
    telegram_id = int(telegram_id)
    if telegram_id <= 0:
        raise APIError("validation_error", "Некорректный Telegram id", detail="telegram_id")

    current = user.get("telegram_id")
    if current is not None and int(current) > 0 and int(current) != telegram_id:
        raise APIError(
            "conflict",
            "Аккаунт уже привязан к другому Telegram. Сначала отвяжите его в приложении.",
            status_code=409,
        )

    other = await db.get_user_by_telegram_id(telegram_id)
    if other and int(other["id"]) != int(user["id"]):
        if other.get("login"):
            raise APIError(
                "conflict",
                "Этот Telegram уже привязан к другому аккаунту.",
                status_code=409,
            )
        await db.clear_user_telegram_identity(int(other["id"]))

    await db.set_user_telegram_identity(int(user["id"]), telegram_id, username)
    await db.mark_telegram_link_token_used(token, _iso(_now()))
    linked = await db.get_user_by_id(int(user["id"]))
    if not linked:
        raise APIError("not_found", "Аккаунт не найден", status_code=404)
    return linked


async def require_linked_user(db: Any, telegram_id: int) -> dict[str, Any]:
    """App user for this Telegram id. Does not create a row."""
    user = await db.get_user_by_telegram_id(int(telegram_id))
    if not user or not user.get("login") or not telegram_linked(user):
        raise APIError("forbidden", LINK_REQUIRED, status_code=403)
    if user.get("is_allowed") is False:
        raise APIError("forbidden", "Аккаунт отключён.", status_code=403)
    return user


async def unlink_telegram(db: Any, user_id: int) -> dict[str, Any]:
    user = await db.get_user_by_id(int(user_id))
    if not user or not user.get("login"):
        raise APIError("not_found", "Пользователь не найден", status_code=404)
    await db.clear_user_telegram_identity(int(user_id))
    updated = await db.get_user_by_id(int(user_id))
    if not updated:
        raise APIError("not_found", "Пользователь не найден", status_code=404)
    return updated
