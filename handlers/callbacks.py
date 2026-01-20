"""
Обработчики callback-запросов (inline-кнопки)
"""
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state
from handlers.states import QueryStates
from handlers.messages import process_final_query
from utils.db_helpers import get_db

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(lambda c: c.data == "confirm_query")
async def confirm_query_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик подтверждения отправки запроса"""
    user_id = callback.from_user.id
    
    # Проверить, что мы в режиме сбора сообщений
    current_state = await state.get_state()
    if current_state != QueryStates.collecting_messages.state:
        await callback.answer("❌ Режим сбора сообщений не активен", show_alert=True)
        return
    
    # Получить собранные данные
    state_data = await state.get_data()
    builder = query_builder_from_state(state_data)
    
    if not builder.has_content():
        await callback.answer("❌ Нет данных для отправки", show_alert=True)
        return
    
    # Собрать финальный запрос
    final_query = builder.build_query()
    
    if not final_query.strip():
        await callback.answer("❌ Запрос пуст", show_alert=True)
        return
    
    # Получить или создать сессию
    db = await get_db()
    user = await db.ensure_user(user_id, callback.from_user.username)
    active_session = await db.get_active_session(user["id"])
    
    if not active_session:
        active_session = await db.create_session(
            user_id=user["id"],
            session_type="query_with_kb",
            status="active"
        )
        logger.info(f"Создана новая сессия #{active_session['id']} для пользователя {user_id}")
    
    session_id = active_session["id"]
    
    # Извлечь пути к прикрепленным файлам для передачи в Cursor CLI
    attached_files = []
    for media in builder.media_files:
        if media.get("file_path"):
            file_path = Path(media["file_path"]) if isinstance(media["file_path"], str) else media["file_path"]
            if file_path.exists():
                attached_files.append(file_path)
    
    # Подтвердить callback
    await callback.answer("✅ Запрос отправляется...")
    
    # Удалить сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Обработать финальный запрос с прикрепленными файлами
    await process_final_query(final_query, callback.message, state, session_id, attached_files=attached_files)
    
    # Сохранить вложения в БД ПОСЛЕ обработки (чтобы они были связаны с правильным сообщением)
    # Получить последнее сообщение пользователя (которое было сохранено в process_final_query)
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
    
    # Очистить состояние
    await state.clear()
    builder.clear()


@router.callback_query(lambda c: c.data == "cancel_query")
async def cancel_query_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены запроса"""
    # Очистить состояние
    await state.clear()
    
    await callback.answer("❌ Запрос отменен")
    
    # Удалить сообщение с кнопками
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    await callback.message.answer("❌ Сбор сообщений отменен. Все данные удалены.")


@router.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик остальных callback-запросов"""
    # TODO: Реализовать обработку других callback-запросов
    # - Обработка отката изменений
    # - Обработка навигации по истории
    # - Обработка управления сессиями
    
    await callback.answer("Функция будет реализована позже")

