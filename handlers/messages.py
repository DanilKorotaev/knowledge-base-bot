"""
Обработчики текстовых сообщений
"""
import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from services.cursor_cli_service import CursorCLIService
from utils.message_helpers import split_long_message

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def text_message_handler(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений"""
    
    # Пропустить команды (они обрабатываются в commands.py)
    if message.text and message.text.startswith('/'):
        return
    
    # Проверить, что есть текст
    if not message.text or not message.text.strip():
        await message.answer("❌ Пожалуйста, отправьте текстовое сообщение.")
        return
    
    user_id = message.from_user.id
    query = message.text.strip()
    
    logger.info(f"Получено текстовое сообщение от пользователя {user_id}: {query[:50]}...")
    
    # Отправить индикатор "печатает..."
    typing_message = await message.answer("⏳ Обрабатываю запрос...")
    
    try:
        # Инициализировать сервис Cursor CLI
        cursor_service = CursorCLIService()
        
        # Обработать запрос через Cursor CLI
        response, changes = await cursor_service.process_query(
            query=query,
            session_id=None  # Пока без сессий, будет реализовано позже
        )
        
        # Удалить индикатор "печатает..."
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        # Отправить ответ пользователю
        # Разбить длинные сообщения на части (лимит Telegram - 4096 символов)
        response_parts = split_long_message(response, max_length=4000)
        
        for i, part in enumerate(response_parts):
            try:
                if i == 0:
                    await message.answer(part, parse_mode="Markdown")
                else:
                    await message.answer(part, parse_mode="Markdown")
            except TelegramBadRequest as e:
                # Если ошибка форматирования Markdown, отправить без форматирования
                logger.warning(f"Ошибка форматирования Markdown: {e}")
                await message.answer(part)
        
        # Если были изменения файлов, сообщить об этом
        if changes:
            changes_info = f"\n\n📝 Изменено файлов: {len(changes)}"
            if len(changes) <= 5:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes])
                changes_info += f"\n{changes_list}"
            else:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes[:5]])
                changes_info += f"\n{changes_list}\n  ... и еще {len(changes) - 5}"
            
            try:
                await message.answer(changes_info)
            except Exception as e:
                logger.warning(f"Не удалось отправить информацию об изменениях: {e}")
        
        logger.info(f"Запрос от пользователя {user_id} обработан успешно")
        
    except Exception as e:
        # Удалить индикатор "печатает..."
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        error_msg = f"❌ Произошла ошибка при обработке запроса: {str(e)}"
        logger.error(f"Ошибка при обработке запроса от пользователя {user_id}: {e}", exc_info=True)
        
        try:
            await message.answer(error_msg)
        except Exception:
            pass

