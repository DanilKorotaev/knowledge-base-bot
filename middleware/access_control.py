"""
Middleware: Telegram работает только от привязанного пользователя приложения.
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import Message, Update, User
from utils.db_helpers import get_db
from kb_app_api.telegram_link import telegram_linked

logger = logging.getLogger(__name__)

_OPEN_COMMANDS = ("/start", "/help", "/link")
_NEED_LINK = (
    "Этот бот отвечает от аккаунта базы знаний.\n\n"
    "В приложении нажмите «Привязать Telegram» и отправьте сюда код:\n"
    "/link КОД\n\n"
    "Если вас пригласили, отправьте код приглашения той же командой."
)


def _event_user(event: Update) -> tuple[Optional[User], Optional[Message]]:
    if event.message and event.message.from_user:
        return event.message.from_user, event.message
    if event.callback_query and event.callback_query.from_user:
        return event.callback_query.from_user, event.callback_query.message
    return None, None


def _is_open_command(message: Optional[Message]) -> bool:
    text = (message.text or "") if message else ""
    return any(text.startswith(cmd) for cmd in _OPEN_COMMANDS)


class AccessControlMiddleware(BaseMiddleware):
    """Пускает только Telegram, привязанный к app-пользователю с login."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        tg_user, message = _event_user(event)
        if not tg_user:
            return await handler(event, data)

        db = await get_db()
        app_user = await db.get_user_by_telegram_id(tg_user.id)
        linked = bool(app_user and app_user.get("login") and telegram_linked(app_user))
        if linked and not app_user.get("is_allowed", True):
            await _deny(event, message, "Аккаунт отключён. Напишите администратору.")
            return
        if linked:
            data["app_user"] = app_user
            return await handler(event, data)

        callback_data = ""
        if event.callback_query and event.callback_query.data:
            callback_data = event.callback_query.data
        if callback_data.startswith("tg_link:"):
            return await handler(event, data)

        if _is_open_command(message):
            return await handler(event, data)

        logger.info(
            "Telegram без привязки: telegram_id=%s username=%s",
            tg_user.id,
            tg_user.username,
        )
        await _deny(event, message, _NEED_LINK)
        return


async def _deny(event: Update, message: Optional[Message], text: str) -> None:
    try:
        if message:
            await message.answer(text)
        elif event.callback_query:
            await event.callback_query.answer(text[:180], show_alert=True)
    except Exception as exc:
        logger.error("Не удалось отправить отказ в доступе: %s", exc)

