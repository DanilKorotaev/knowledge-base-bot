"""
Утилиты для стандартизированной обработки ошибок
"""
import logging
from typing import Optional
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)


def escape_html(text: str) -> str:
    """
    Экранировать HTML-специальные символы
    
    Args:
        text: Текст для экранирования
    
    Returns:
        str: Экранированный текст
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_error_message(
    event: Message | CallbackQuery,
    error: Exception,
    user_message: Optional[str] = None,
    log_message: Optional[str] = None,
    reply_markup=None,
    use_html: bool = True
) -> None:
    """
    Стандартизированная отправка сообщения об ошибке
    
    Args:
        event: Объект Message или CallbackQuery
        error: Исключение
        user_message: Сообщение для пользователя (если None, используется стандартное)
        log_message: Сообщение для лога (если None, используется стандартное)
        reply_markup: Клавиатура для ответа
        use_html: Использовать ли HTML форматирование
    """
    # Логирование ошибки
    if log_message:
        logger.error(f"{log_message}: {error}", exc_info=True)
    else:
        logger.error(f"Ошибка: {error}", exc_info=True)
    
    # Формирование сообщения для пользователя
    if user_message:
        error_text = user_message
    else:
        error_text = "❌ Произошла ошибка. Попробуйте позже или обратитесь к администратору."
    
    # Экранирование HTML, если используется HTML
    if use_html:
        error_text = escape_html(error_text)
        parse_mode = ParseMode.HTML
    else:
        parse_mode = None
    
    # Отправка сообщения
    try:
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(
                error_text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif isinstance(event, Message):
            await event.answer(
                error_text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
    except Exception as e:
        # Если не удалось отправить через edit_text, попробуем answer
        logger.warning(f"Не удалось отправить сообщение об ошибке через edit_text: {e}")
        try:
            if isinstance(event, CallbackQuery):
                await event.message.answer(
                    error_text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
        except Exception as e2:
            logger.error(f"Критическая ошибка при отправке сообщения об ошибке: {e2}")


async def handle_error_silently(
    error: Exception,
    log_message: Optional[str] = None,
    log_level: str = "warning"
) -> None:
    """
    Тихая обработка ошибки (только логирование, без уведомления пользователя)
    
    Args:
        error: Исключение
        log_message: Сообщение для лога
        log_level: Уровень логирования ("error", "warning", "info", "debug")
    """
    if log_message:
        message = f"{log_message}: {error}"
    else:
        message = f"Ошибка: {error}"
    
    if log_level == "error":
        logger.error(message, exc_info=True)
    elif log_level == "warning":
        logger.warning(message)
    elif log_level == "info":
        logger.info(message)
    else:
        logger.debug(message)

