"""
Middleware для проверки доступа пользователей
"""
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, Update
from config import config
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)


class AccessControlMiddleware(BaseMiddleware):
    """Middleware для проверки доступа пользователей"""
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка доступа перед обработкой события"""
        
        # Если режим открытый - пропускаем всех
        if config.ACCESS_MODE == "open":
            return await handler(event, data)
        
        # Получить пользователя из события
        user = None
        message = None
        
        if event.message:
            user = event.message.from_user
            message = event.message
        elif event.callback_query:
            user = event.callback_query.from_user
            message = event.callback_query.message
        
        if not user:
            # Если нет пользователя, пропускаем (например, для других типов событий)
            return await handler(event, data)
        
        # Разрешенные команды для всех (даже неавторизованных)
        allowed_commands = ["/start", "/help"]
        if message and message.text and any(message.text.startswith(cmd) for cmd in allowed_commands):
            return await handler(event, data)
        
        # Проверка доступа
        db = await get_db()
        user_id = user.id
        
        if not await db.is_user_allowed(user_id):
            try:
                if message:
                    await message.answer(
                        "❌ У вас нет доступа к этому боту.\n\n"
                        "Обратитесь к администратору для получения доступа."
                    )
                elif event.callback_query:
                    await event.callback_query.answer(
                        "❌ У вас нет доступа к этому боту.",
                        show_alert=True
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения об отказе в доступе: {e}")
            
            logger.warning(
                f"Попытка доступа от неавторизованного пользователя: "
                f"telegram_id={user_id}, username={user.username}"
            )
            return  # Прерываем обработку
        
        return await handler(event, data)

