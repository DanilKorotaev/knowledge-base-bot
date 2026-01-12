"""
Обработчики текстовых сообщений
"""
import logging
import time
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

from services.cursor_cli_service import CursorCLIService
from services.sync_service import SyncService
from utils.message_helpers import split_long_message, markdown_to_html, escape_markdown_v2

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
    
    start_time = time.time()
    
    try:
        # Проверить актуальность базы знаний (быстрая синхронизация из NextCloud)
        sync_service = SyncService()
        sync_updated = False
        
        sync_start = time.time()
        if sync_service.enabled:
            try:
                # Быстрая синхронизация (показываем уведомление только если синхронизация долгая)
                # Обновляем сообщение, если синхронизация началась
                async def notify_sync(msg: str, is_important: bool = False):
                    """Callback для уведомлений о синхронизации"""
                    if is_important or "Синхронизирую" in msg:
                        try:
                            await typing_message.edit_text(f"⏳ {msg}")
                        except Exception:
                            pass
                
                sync_service.set_notify_callback(notify_sync)
                
                # Быстрая синхронизация из NextCloud (только если включена AUTO_SYNC)
                from config import config
                if config.AUTO_SYNC:
                    sync_updated = await sync_service.sync_from_nextcloud(show_notification=True)
            except Exception as e:
                logger.warning(f"Ошибка при проверке синхронизации: {e}")
        
        sync_time = time.time() - sync_start
        if sync_time > 1.0:
            logger.info(f"⏱️ Синхронизация заняла: {sync_time:.2f}с")
        
        # Инициализировать сервис Cursor CLI
        cursor_start = time.time()
        cursor_service = CursorCLIService()
        
        # Обработать запрос через Cursor CLI
        response, changes = await cursor_service.process_query(
            query=query,
            session_id=None  # Пока без сессий, будет реализовано позже
        )
        
        cursor_time = time.time() - cursor_start
        logger.info(f"⏱️ Cursor CLI обработка заняла: {cursor_time:.2f}с")
        
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
                # Используем HTML для более надежного форматирования
                # Конвертируем Markdown в HTML
                html_part = markdown_to_html(part)
                await message.answer(html_part, parse_mode=ParseMode.HTML)
            except TelegramBadRequest as e:
                # Если ошибка форматирования HTML, пробуем Markdown V2
                logger.warning(f"Ошибка форматирования HTML: {e}, пробую Markdown V2")
                try:
                    md_part = escape_markdown_v2(part)
                    await message.answer(md_part, parse_mode=ParseMode.MARKDOWN_V2)
                except TelegramBadRequest as e2:
                    # Если и Markdown V2 не работает, отправляем без форматирования
                    logger.warning(f"Ошибка форматирования Markdown V2: {e2}, отправляю без форматирования")
                await message.answer(part)
        
        # Если были изменения файлов, синхронизировать с NextCloud
        if changes:
            # Синхронизировать изменения с NextCloud
            sync_success = await sync_service.sync_changes(changes)
            
            changes_info = f"\n\n📝 Изменено файлов: {len(changes)}"
            if len(changes) <= 5:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes])
                changes_info += f"\n{changes_list}"
            else:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes[:5]])
                changes_info += f"\n{changes_list}\n  ... и еще {len(changes) - 5}"
            
            if sync_success:
                changes_info += "\n✅ Изменения синхронизированы с NextCloud"
            else:
                changes_info += "\n⚠️ Не удалось синхронизировать с NextCloud"
            
            try:
                await message.answer(changes_info)
            except Exception as e:
                logger.warning(f"Не удалось отправить информацию об изменениях: {e}")
        
        total_time = time.time() - start_time
        logger.info(f"✅ Запрос от пользователя {user_id} обработан успешно за {total_time:.2f}с")
        
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

