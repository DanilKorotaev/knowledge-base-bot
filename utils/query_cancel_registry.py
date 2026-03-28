"""
Реестр активных запросов к Cursor CLI для отмены по callback (inline-кнопка).

callback_data: cq:<request_id>, где request_id — 16 hex-символов.
"""
import secrets
from typing import Dict, Tuple
import asyncio

# request_id -> (telegram_user_id, asyncio.Event для отмены)
_registry: Dict[str, Tuple[int, asyncio.Event]] = {}


def register_cancel_request(user_id: int) -> Tuple[str, asyncio.Event]:
    """Зарегистрировать запрос; вернуть request_id и Event, который выставится при отмене."""
    request_id = secrets.token_hex(8)
    ev = asyncio.Event()
    _registry[request_id] = (user_id, ev)
    return request_id, ev


def unregister_cancel_request(request_id: str) -> None:
    _registry.pop(request_id, None)


def try_cancel_query(user_id: int, request_id: str) -> bool:
    """
    Запросить отмену. True, если запрос найден и user_id совпадает.
    """
    entry = _registry.get(request_id)
    if not entry:
        return False
    owner_id, ev = entry
    if owner_id != user_id:
        return False
    ev.set()
    return True
