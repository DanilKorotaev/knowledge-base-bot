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
from utils.db_helpers import get_db
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state
from handlers.states import QueryStates
from handlers.keyboards import get_confirm_query_keyboard

router = Router()
logger = logging.getLogger(__name__)


async def process_final_query(
    query: str,
    message: Message,
    state: FSMContext,
    session_id: int
):
    """Обработать финальный запрос через Cursor CLI"""
    from utils.db_helpers import get_db
    
    db = await get_db()
    
    # Сохранить сообщение пользователя в сессию
    await db.add_message(session_id, "user", query)
    
    # Получить историю сообщений сессии для контекста
    session_messages = await db.get_session_messages(session_id)
    logger.debug(f"Загружена история сессии: {len(session_messages)} сообщений")
    
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
                async def notify_sync(msg: str, is_important: bool = False):
                    """Callback для уведомлений о синхронизации"""
                    if is_important or "Синхронизирую" in msg:
                        try:
                            await typing_message.edit_text(f"⏳ {msg}")
                        except Exception:
                            pass
                
                sync_service.set_notify_callback(notify_sync)
                
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
        
        # Обработать запрос через Cursor CLI с контекстом сессии
        response, changes = await cursor_service.process_query(
            query=query,
            session_id=session_id,
            session_messages=session_messages
        )
        
        cursor_time = time.time() - cursor_start
        logger.info(f"⏱️ Cursor CLI обработка заняла: {cursor_time:.2f}с")
        
        # Удалить индикатор "печатает..."
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        # Отправить ответ пользователю
        response_parts = split_long_message(response, max_length=4000)
        
        for i, part in enumerate(response_parts):
            try:
                html_part = markdown_to_html(part)
                await message.answer(html_part, parse_mode=ParseMode.HTML)
            except TelegramBadRequest as e:
                logger.warning(f"Ошибка форматирования HTML: {e}, пробую Markdown V2")
                try:
                    md_part = escape_markdown_v2(part)
                    await message.answer(md_part, parse_mode=ParseMode.MARKDOWN_V2)
                except TelegramBadRequest as e2:
                    logger.warning(f"Ошибка форматирования Markdown V2: {e2}, отправляю без форматирования")
                    await message.answer(part)
        
        # Сохранить ответ ассистента в сессию
        await db.add_message(session_id, "assistant", response)
        
        # Если были изменения файлов, залогировать их и синхронизировать с NextCloud
        if changes:
            for change in changes:
                await db.log_file_change(
                    session_id=session_id,
                    file_path=change.get("path", ""),
                    change_type=change.get("type", "modified"),
                    old_content=change.get("old_content"),
                    new_content=change.get("new_content")
                )
            
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
        logger.info(f"✅ Запрос обработан успешно за {total_time:.2f}с")
        
    except Exception as e:
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        error_msg = f"❌ Произошла ошибка при обработке запроса: {str(e)}"
        logger.error(f"Ошибка при обработке запроса: {e}", exc_info=True)
        
        try:
            await message.answer(error_msg)
        except Exception:
            pass


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
    
    # Проверить режим сбора сообщений
    current_state = await state.get_state()
    if current_state == QueryStates.collecting_messages.state:
        # Режим сбора сообщений - сохранить во временное хранилище
        state_data = await state.get_data()
        builder = query_builder_from_state(state_data) if state_data.get("text_parts") else QueryBuilder()
        
        builder.add_text(query)
        
        # Сохранить обратно в состояние
        await state.update_data(**query_builder_to_state(builder))
        
        # Показать кнопку подтверждения
        summary = builder.get_summary()
        await message.answer(
            f"✅ Текстовое сообщение добавлено.\n\n{summary}\n\n"
            f"Продолжайте добавлять сообщения или подтвердите отправку.",
            reply_markup=get_confirm_query_keyboard()
        )
        return
    
    # Обычный режим - обработать сразу
    logger.info(f"Получено текстовое сообщение от пользователя {user_id}: {query[:50]}...")
    
    # Получить или создать сессию
    db = await get_db()
    user = await db.ensure_user(user_id, message.from_user.username)
    active_session = await db.get_active_session(user["id"])
    
    # Если нет активной сессии, создать новую с контекстом БЗ по умолчанию
    if not active_session:
        active_session = await db.create_session(
            user_id=user["id"],
            session_type="query_with_kb",
            status="active"
        )
        logger.info(f"Создана новая сессия #{active_session['id']} для пользователя {user_id}")
    
    session_id = active_session["id"]
    
    # Обработать запрос
    await process_final_query(query, message, state, session_id)

