"""Helpers for API user identity fields that still expect telegram_user_id."""
from __future__ import annotations

from typing import Any


def telegram_id_for_jobs(user: dict[str, Any]) -> int:
    tid = user.get("telegram_id")
    if tid is not None:
        return int(tid)
    return -int(user["id"])
