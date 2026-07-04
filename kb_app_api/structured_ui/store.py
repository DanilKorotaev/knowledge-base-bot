"""In-memory structured_ui payloads keyed by assistant message id (MVP; replace with DB later)."""

from __future__ import annotations

from typing import Any

_screens_by_message_id: dict[int, dict[str, Any]] = {}


def set_for_message(message_id: int, screen: dict[str, Any]) -> None:
    _screens_by_message_id[int(message_id)] = screen


def get_for_message(message_id: int) -> dict[str, Any] | None:
    return _screens_by_message_id.get(int(message_id))


def screens_by_message_ids(message_ids: list[int]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for mid in message_ids:
        screen = get_for_message(mid)
        if screen is not None:
            out[int(mid)] = screen
    return out


def clear_all() -> None:
    _screens_by_message_id.clear()
