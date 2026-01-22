"""
Middleware и декораторы для проверки прав администратора
"""
import logging
from functools import wraps
from typing import Callable, Awaitable, Any
from aiogram.types import Message, CallbackQuery
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)


def require_admin(handler: Callable) -> Callable:
    """
    Декоратор для проверки прав администратора перед выполнением обработчика
    
    Использование:
        @router.callback_query(lambda c: c.data == "admin_action")
        @require_admin
        async def admin_handler(callback: CallbackQuery):
            # Код обработчика
            pass
    """
    @wraps(handler)
    async def wrapper(*args, **kwargs):
        # Определить тип события и получить user_id
        user_id = None
        event = None
        
        # Проверить аргументы
        for arg in args:
            if isinstance(arg, Message):
                user_id = arg.from_user.id
                event = arg
                break
            elif isinstance(arg, CallbackQuery):
                user_id = arg.from_user.id
                event = arg
                break
        
        if not user_id:
            logger.error("Не удалось определить user_id в декораторе require_admin")
            return
        
        # Проверить права администратора
        db = await get_db()
        is_admin = await db.is_user_admin(user_id)
        
        if not is_admin:
            error_msg = "❌ У вас нет прав администратора."
            
            # Отправить ответ в зависимости от типа события
            if isinstance(event, CallbackQuery):
                await event.answer(error_msg, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(error_msg)
            
            logger.warning(f"Попытка доступа к административной функции от пользователя {user_id}")
            return
        
        # Выполнить обработчик
        return await handler(*args, **kwargs)
    
    return wrapper

