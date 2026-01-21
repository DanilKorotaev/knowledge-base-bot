"""
Обработчики текстовых сообщений
"""
import logging
import time
from pathlib import Path
from typing import Optional, List
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
from handlers.keyboards import (
    get_confirm_query_keyboard, get_main_keyboard, get_collecting_messages_keyboard,
    get_active_session_keyboard
)

router = Router()
logger = logging.getLogger(__name__)


async def process_final_query(
    query: str,
    message: Message,
    state: FSMContext,
    session_id: int,
    attached_files: Optional[List[Path]] = None
):
    """
    Обработать финальный запрос через Cursor CLI
    
    Args:
        query: Текст запроса
        message: Объект сообщения Telegram
        state: Состояние FSM
        session_id: ID сессии
        attached_files: Список путей к прикрепленным файлам (опционально)
    """
    from utils.db_helpers import get_db
    
    db = await get_db()
    
    # Получить историю сообщений сессии для контекста (ПЕРЕД сохранением текущего сообщения)
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
        
        # Обработать запрос через Cursor CLI с контекстом сессии и прикрепленными файлами
        response, changes = await cursor_service.process_query(
            query=query,
            session_id=session_id,
            session_messages=session_messages,
            attached_files=attached_files
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
        
        # Сохранить сообщение пользователя в сессию (ПОСЛЕ обработки, чтобы избежать дублирования в контексте)
        await db.add_message(session_id, "user", query)
        
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
                await message.answer(changes_info, reply_markup=get_active_session_keyboard())
            except Exception as e:
                logger.warning(f"Не удалось отправить информацию об изменениях: {e}")
        else:
            # Если изменений не было, показать клавиатуру активной сессии отдельным сообщением
            try:
                await message.answer(
                    "💡 Используйте кнопки ниже для управления сессией.",
                    reply_markup=get_active_session_keyboard()
                )
            except Exception:
                pass  # Игнорируем ошибки
        
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


# Обработчики кнопок главного меню
# Эти кнопки теперь обрабатываются через inline-меню главного меню


# Эти кнопки теперь обрабатываются через inline-меню главного меню


@router.message(lambda m: m.text == "🏠 Главное меню")
async def main_menu_button_handler(message: Message):
    """Обработка кнопки 'Главное меню'"""
    from handlers.keyboards import get_main_menu_inline_keyboard_with_admin
    
    db = await get_db()
    user_id = message.from_user.id
    is_admin = await db.is_user_admin(user_id)
    
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_inline_keyboard_with_admin(is_admin=is_admin),
        parse_mode=ParseMode.HTML
    )


@router.message(lambda m: m.text == "❌ Отмена")
async def cancel_button_handler(message: Message, state: FSMContext):
    """Обработка кнопки 'Отмена' для FSM-состояний"""
    current_state = await state.get_state()
    
    # Если режим сбора сообщений - очистить состояние
    if current_state == QueryStates.collecting_messages.state:
        await state.clear()
        await message.answer(
            "❌ Режим сбора сообщений отменен.\nВсе собранные данные удалены.",
            reply_markup=get_main_keyboard()
        )
    else:
        await state.clear()
        await message.answer(
            "❌ Операция отменена.",
            reply_markup=get_main_keyboard()
        )


@router.message(lambda m: m.text == "✅ Завершить сбор")
async def finish_collect_button_handler(message: Message, state: FSMContext):
    """Обработка кнопки 'Завершить сбор' - завершает режим сбора и отправляет запрос"""
    current_state = await state.get_state()
    
    if current_state != QueryStates.collecting_messages.state:
        await message.answer(
            "ℹ️ Режим сбора сообщений не активен.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Получить собранные данные
    state_data = await state.get_data()
    builder = query_builder_from_state(state_data)
    
    if not builder.has_content():
        await message.answer(
            "❌ Нет данных для отправки. Добавьте сообщения перед завершением сбора.",
            reply_markup=get_collecting_messages_keyboard()
        )
        return
    
    # Собрать финальный запрос
    final_query = builder.build_query()
    
    if not final_query.strip():
        await message.answer(
            "❌ Запрос пуст. Добавьте сообщения перед завершением сбора.",
            reply_markup=get_collecting_messages_keyboard()
        )
        return
    
    # Получить или создать сессию
    db = await get_db()
    user_id = message.from_user.id
    user = await db.ensure_user(user_id, message.from_user.username)
    active_session = await db.get_active_session(user["id"])
    
    if not active_session:
        active_session = await db.create_session(
            user_id=user["id"],
            session_type="query_with_kb",
            status="active"
        )
        logger.info(f"Создана новая сессия #{active_session['id']} для пользователя {user_id}")
    
    session_id = active_session["id"]
    
    # Извлечь пути к прикрепленным файлам
    attached_files = []
    for media in builder.media_files:
        if media.get("file_path"):
            file_path = Path(media["file_path"]) if isinstance(media["file_path"], str) else media["file_path"]
            if file_path.exists():
                attached_files.append(file_path)
    
    # Очистить состояние перед обработкой
    await state.clear()
    
    # Обработать финальный запрос
    await process_final_query(final_query, message, state, session_id, attached_files=attached_files)
    
    # Сохранить вложения в БД ПОСЛЕ обработки
    user_messages = await db.get_session_messages(session_id)
    last_user_message = None
    for msg in reversed(user_messages):
        if msg.get("role") == "user":
            last_user_message = msg
            break
    
    if last_user_message:
        for voice in builder.voice_files:
            if voice.get("file_path"):
                attachment = await db.add_attachment(
                    session_id=session_id,
                    message_id=last_user_message["id"],
                    file_type="voice",
                    file_id=voice.get("file_id", ""),
                    file_path=str(voice["file_path"]) if voice.get("file_path") else None,
                    file_name=f"{voice.get('file_id', 'voice')}.ogg"
                )
                if voice.get("transcription"):
                    await db.add_transcription(
                        attachment_id=attachment["id"],
                        text=voice["transcription"],
                        language=None
                    )
        
        for media in builder.media_files:
            if media.get("file_path"):
                await db.add_attachment(
                    session_id=session_id,
                    message_id=last_user_message["id"],
                    file_type=media.get("file_type", "file"),
                    file_id=media.get("file_id", ""),
                    file_path=str(media["file_path"]) if media.get("file_path") else None,
                    file_name=media.get("file_name", "")
                )
    
    builder.clear()


@router.message(lambda m: m.text == "📝 Режим сбора")
async def collect_mode_button_handler(message: Message, state: FSMContext):
    """Обработка кнопки 'Режим сбора'"""
    from handlers.commands import collect_mode_handler
    await collect_mode_handler(message, state)


# Эти действия теперь доступны через детали сессии в inline-меню


@router.message()
async def text_message_handler(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений"""
    
    # Пропустить команды (они обрабатываются в commands.py)
    if message.text and message.text.startswith('/'):
        return
    
    # Пропустить сообщения с выбранными пользователями (обрабатываются в commands.py)
    # Проверяем различные возможные поля для users_requested
    if (hasattr(message, 'users_requested') and message.users_requested) or \
       (hasattr(message, 'users_shared') and message.users_shared):
        return
    
    # Пропустить сообщения с контактами (обрабатываются в commands.py)
    if message.contact:
        return
    
    # Пропустить кнопки (они обрабатываются выше или через inline-меню)
    menu_buttons = [
        "🏠 Главное меню", "❌ Отмена", "✅ Завершить сбор", "📝 Режим сбора"
    ]
    if message.text in menu_buttons:
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
        
        # Показать информацию о добавленном сообщении
        summary = builder.get_summary()
        await message.answer(
            f"✅ Текстовое сообщение добавлено.\n\n{summary}\n\n"
            f"Продолжайте добавлять сообщения или нажмите '✅ Завершить сбор' для отправки.",
            reply_markup=get_collecting_messages_keyboard(),
            parse_mode=None  # Явно указываем отсутствие форматирования
        )
        # Также показать inline-кнопку для быстрой отправки
        await message.answer(
            "Готовы отправить запрос?",
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
    
    # Клавиатура активной сессии будет показана автоматически в process_final_query

