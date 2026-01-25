"""
Обработчики текстовых сообщений
"""
import logging
from pathlib import Path
from typing import Optional, List

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.keyboards import (
    get_confirm_query_keyboard, get_main_keyboard, get_collecting_messages_keyboard
)
from handlers.states import QueryStates
from services.query_processing_service import QueryProcessingService
from services.session_service import SessionService
from utils.constants import SessionType
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state

router = Router()
logger = logging.getLogger(__name__)


# Обработчики кнопок главного меню
# Эти кнопки теперь обрабатываются через inline-меню главного меню


# Эти кнопки теперь обрабатываются через inline-меню главного меню


@router.message(lambda m: m.text == "🏠 Главное меню")
async def main_menu_button_handler(message: Message):
    """Обработка кнопки 'Главное меню'"""
    from handlers.keyboards import (
        get_main_menu_inline_keyboard_with_admin,
        format_active_session_info
    )
    from utils.db_helpers import get_db
    
    db = await get_db()
    user_id = message.from_user.id
    is_admin = await db.is_user_admin(user_id)
    
    # Получить активную сессию
    user = await db.ensure_user(user_id, message.from_user.username)
    active_session = await db.get_active_session(user["id"])
    
    # Сформировать текст меню с информацией об активной сессии
    menu_text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    if active_session:
        menu_text += format_active_session_info(active_session)
    
    await message.answer(
        menu_text,
        reply_markup=get_main_menu_inline_keyboard_with_admin(
            is_admin=is_admin,
            active_session=active_session
        ),
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
    user_id = message.from_user.id
    session_service = SessionService()
    active_session = await session_service.get_or_create_active_session(
        user_id=user_id,
        username=message.from_user.username,
        session_type=SessionType.QUERY_WITH_KB
    )
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
    query_service = QueryProcessingService()
    await query_service.process_query(
        query=final_query,
        session_id=session_id,
        message=message,
        attached_files=attached_files
    )
    
    # Сохранить вложения в БД ПОСЛЕ обработки
    from utils.db_helpers import get_db
    from utils.constants import MessageRole
    
    db = await get_db()
    user_messages = await db.get_session_messages(session_id)
    last_user_message = None
    for msg in reversed(user_messages):
        if msg.get("role") == str(MessageRole.USER):
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
    session_service = SessionService()
    active_session = await session_service.get_or_create_active_session(
        user_id=user_id,
        username=message.from_user.username,
        session_type=SessionType.QUERY_WITH_KB
    )
    session_id = active_session["id"]
    
    # Обработать запрос
    query_service = QueryProcessingService()
    await query_service.process_query(
        query=query,
        session_id=session_id,
        message=message
    )
    
    # Клавиатура активной сессии будет показана автоматически в QueryProcessingService

