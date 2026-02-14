"""
Обработчики callback-запросов (inline-кнопки)
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Contact

from config import config
from handlers.keyboards import (
    get_main_keyboard, get_sessions_keyboard, get_history_keyboard,
    get_revert_session_keyboard, get_delete_session_keyboard, get_session_details_keyboard,
    get_admin_menu_keyboard, get_users_selection_keyboard, get_admin_contact_request_keyboard,
    get_main_menu_inline_keyboard_with_admin, get_cancel_keyboard,
    get_collecting_messages_keyboard, get_enable_collect_mode_keyboard
)
from handlers.states import QueryStates, AdminStates
from middleware.admin_middleware import require_admin
from services.query_processing_service import QueryProcessingService
from services.session_service import SessionService
from utils.constants import SessionType, SessionStatus, MessageRole
from utils.db_helpers import get_db
from utils.error_helpers import send_error_message
from utils.file_helpers import write_file_content, read_file_content
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state
from utils.session_helpers import get_user_sessions_for_display, format_sessions_list, format_session_details
from utils.telegram_helpers import FakeMessage

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
    session_service = SessionService()
    active_session = await session_service.get_or_create_active_session(
        user_id=user_id,
        username=callback.from_user.username,
        session_type=SessionType.QUERY_WITH_KB
    )
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
    query_service = QueryProcessingService()
    await query_service.process_query(
        query=final_query,
        session_id=session_id,
        message=callback.message,
        attached_files=attached_files
    )
    
    # Сохранить вложения в БД ПОСЛЕ обработки (чтобы они были связаны с правильным сообщением)
    # Получить последнее сообщение пользователя (которое было сохранено в QueryProcessingService)
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


# Обработчики управления сессиями
@router.callback_query(lambda c: c.data.startswith("switch_session_"))
async def switch_session_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка переключения сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Проверить, что сессия принадлежит пользователю
    if session["user_id"] != user["id"]:
        await callback.answer("❌ Эта сессия не принадлежит вам", show_alert=True)
        return
    
    # Деактивировать текущую активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session and active_session["id"] != session_id:
        await db.update_session(active_session["id"], status="completed")
    
    # Активировать выбранную сессию
    await db.update_session(session_id, status="active")
    await state.update_data(session_id=session_id)
    
    # Показать детали сессии после переключения
    messages = await db.get_session_messages(session_id)
    session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
    
    response = f"✅ <b>Переключено на сессию #{session_id}</b>\n\n"
    response += f"Статус: 🟢 Активна\n"
    response += f"Тип: {session_type_label}\n"
    response += f"Сообщений: {len(messages)}\n"
    response += f"Создана: {session['created_at']}\n\n"
    
    if messages:
        response += "<b>Последние сообщения:</b>\n"
        for msg in messages[-3:]:  # Показать последние 3
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            text_preview = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
            response += f"{role_emoji} {text_preview}\n"
    
    await callback.message.edit_text(
        response,
        parse_mode=ParseMode.HTML,
        reply_markup=get_session_details_keyboard(session_id, is_active=True)
    )


@router.callback_query(lambda c: c.data.startswith("session_details_"))
async def session_details_callback(callback: CallbackQuery):
    """Обработка клика на сессию - показываем детали с кнопками действий"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Проверить, активна ли сессия
    active_session = await db.get_active_session(user["id"])
    is_active = active_session and active_session["id"] == session_id
    
    # Получить сообщения сессии
    messages = await db.get_session_messages(session_id)
    
    session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
    status_label = "🟢 Активна" if is_active else f"⚪ {session['status']}"
    
    response = f"<b>Сессия #{session_id}</b>\n\n"
    response += f"Статус: {status_label}\n"
    response += f"Тип: {session_type_label}\n"
    response += f"Сообщений: {len(messages)}\n"
    response += f"Создана: {session['created_at']}\n\n"
    
    if messages:
        response += "<b>Последние сообщения:</b>\n"
        for msg in messages[-3:]:  # Показать последние 3
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            text_preview = msg["content"][:60] + "..." if len(msg["content"]) > 60 else msg["content"]
            response += f"{role_emoji} {text_preview}\n"
    
    keyboard = get_session_details_keyboard(session_id, is_active)
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("view_session_"))
async def view_session_callback(callback: CallbackQuery):
    """Обработка просмотра подробностей сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Проверить, активна ли сессия
    active_session = await db.get_active_session(user["id"])
    is_active = active_session and active_session["id"] == session_id
    
    # Получить сообщения сессии
    messages = await db.get_session_messages(session_id)
    
    session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
    status_label = "🟢 Активна" if is_active else f"⚪ {session['status']}"
    
    response = f"<b>Подробности сессии #{session_id}</b>\n\n"
    response += f"Статус: {status_label}\n"
    response += f"Тип: {session_type_label}\n"
    response += f"Сообщений: {len(messages)}\n"
    response += f"Создана: {session['created_at']}\n\n"
    
    if messages:
        response += "<b>Все сообщения:</b>\n\n"
        for i, msg in enumerate(messages[-10:], 1):  # Показать последние 10
            role_emoji = "👤" if msg["role"] == "user" else "🤖"
            role_label = "Пользователь" if msg["role"] == "user" else "Ассистент"
            text_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            response += f"{i}. {role_emoji} <b>{role_label}:</b>\n{text_preview}\n\n"
    
    keyboard = get_session_details_keyboard(session_id, is_active)
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("delete_session_"))
async def delete_session_callback(callback: CallbackQuery):
    """Обработка запроса на удаление сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Показать подтверждение удаления
    keyboard = get_delete_session_keyboard(session_id)
    await callback.message.edit_text(
        f"⚠️ Вы уверены, что хотите удалить сессию #{session_id}?\n\n"
        f"Это действие нельзя отменить.",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("confirm_delete_session_"))
async def confirm_delete_session_callback(callback: CallbackQuery):
    """Обработка подтверждения удаления сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # TODO: Реализовать удаление сессии из БД (если есть метод delete_session)
    # Пока просто деактивируем
    await db.update_session(session_id, status="deleted")
    
    # Вернуться к списку сессий
    from handlers.commands import sessions_handler
    fake_message = FakeMessage(callback)
    await sessions_handler(fake_message)
    
    # Удалить старое сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(lambda c: c.data.startswith("end_session_"))
async def end_session_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка завершения сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Завершить сессию
    await db.update_session(session_id, status="completed")
    
    # Если это была активная сессия, очистить состояние
    active_session = await db.get_active_session(user["id"])
    if active_session and active_session["id"] == session_id:
        await state.update_data(session_id=None)
    
    # Вернуться к списку сессий
    from handlers.commands import sessions_handler
    fake_message = FakeMessage(callback)
    await sessions_handler(fake_message)
    
    # Удалить старое сообщение
    try:
        await callback.message.delete()
    except Exception:
        pass


@router.callback_query(lambda c: c.data.startswith("sessions_page_"))
async def sessions_page_callback(callback: CallbackQuery):
    """Обработка навигации по страницам сессий"""
    await callback.answer()
    
    try:
        page = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный номер страницы", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессии для отображения с пагинацией
    page_sessions, active_session_id, total_count = await get_user_sessions_for_display(
        user_id=user["id"],
        page=page,
        per_page=5,
        limit=20
    )
    
    if not page_sessions:
        await callback.message.edit_text(
            "ℹ️ У вас нет сессий.",
            reply_markup=None
        )
        return
    
    # Форматировать список сессий
    response = format_sessions_list(
        sessions=page_sessions,
        active_session_id=active_session_id,
        page=page,
        per_page=5,
        total_count=total_count
    )
    
    # Получить все сессии для клавиатуры (нужны для навигации)
    all_sessions = await db.get_user_sessions(user["id"], limit=20)
    sessions = [s for s in all_sessions if s.get("status") != str(SessionStatus.DELETED)]
    
    keyboard = get_sessions_keyboard(sessions, page=page)
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# Обработчики истории изменений
@router.callback_query(lambda c: c.data.startswith("history_page_"))
async def history_page_callback(callback: CallbackQuery):
    """Обработка навигации по страницам истории изменений"""
    await callback.answer()
    
    try:
        parts = callback.data.split("_")
        page = int(parts[2])
        session_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверные параметры", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Проверить, что сессия принадлежит пользователю
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Получить изменения сессии
    changes = await db.get_file_changes(session_id=session_id)
    
    if not changes:
        await callback.message.edit_text(
            f"📜 История изменений сессии #{session_id}\n\n"
            "ℹ️ В этой сессии пока нет изменений файлов.",
            reply_markup=None
        )
        return
    
    # Форматировать историю для текущей страницы
    per_page = 5
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_changes = changes[start_idx:end_idx]
    
    response = f"📜 <b>История изменений сессии #{session_id}</b>\n\n"
    
    change_type_labels = {
        "created": "➕ Создан",
        "modified": "✏️ Изменен",
        "deleted": "🗑 Удален"
    }
    
    for change in page_changes:
        change_type_label = change_type_labels.get(change["change_type"], "📄 Изменен")
        file_name = change["file_path"].split("/")[-1]
        created_at = change["created_at"]
        
        response += f"<b>{file_name}</b> - {change_type_label}\n"
        response += f"  Время: {created_at}\n\n"
    
    if len(changes) > per_page:
        response += f"\n<i>Страница {page + 1}. Показано {len(page_changes)} из {len(changes)} изменений.</i>"
    
    keyboard = get_history_keyboard(changes, session_id, page=page)
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(lambda c: c.data.startswith("view_change_"))
async def view_change_callback(callback: CallbackQuery):
    """Обработка просмотра деталей изменения"""
    await callback.answer()
    
    try:
        change_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID изменения", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить изменение
    change = await db.get_file_change(change_id)
    if not change:
        await callback.answer("❌ Изменение не найдено", show_alert=True)
        return
    
    # Проверить, что сессия принадлежит пользователю
    session = await db.get_session(change["session_id"])
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    change_type_labels = {
        "created": "➕ Создан",
        "modified": "✏️ Изменен",
        "deleted": "🗑 Удален"
    }
    
    response = f"<b>Детали изменения #{change_id}</b>\n\n"
    response += f"Файл: <code>{change['file_path']}</code>\n"
    response += f"Тип: {change_type_labels.get(change['change_type'], '📄 Изменен')}\n"
    response += f"Время: {change['created_at']}\n\n"
    
    if change["old_content"]:
        old_preview = change["old_content"][:200] + "..." if len(change["old_content"]) > 200 else change["old_content"]
        response += f"<b>Старое содержимое:</b>\n<code>{old_preview}</code>\n\n"
    
    if change["new_content"]:
        new_preview = change["new_content"][:200] + "..." if len(change["new_content"]) > 200 else change["new_content"]
        response += f"<b>Новое содержимое:</b>\n<code>{new_preview}</code>"
    
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=None)


# Обработчики отката изменений
@router.callback_query(lambda c: c.data.startswith("revert_") and not c.data.startswith("revert_session_"))
async def revert_change_callback(callback: CallbackQuery):
    """Обработка отката конкретного изменения"""
    await callback.answer()
    
    try:
        change_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID изменения", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить изменение
    change = await db.get_file_change(change_id)
    if not change:
        await callback.answer("❌ Изменение не найдено", show_alert=True)
        return
    
    # Проверить, что сессия принадлежит пользователю
    session = await db.get_session(change["session_id"])
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    
    # Выполнить откат
    # file_path в БД хранится как относительный путь от LOCAL_KB_PATH
    file_path = Path(config.LOCAL_KB_PATH) / change["file_path"]
    
    try:
        if change["change_type"] == "created":
            # Удалить файл
            if file_path.exists():
                file_path.unlink()
        elif change["change_type"] == "deleted":
            # Восстановить файл
            if change["old_content"]:
                write_file_content(file_path, change["old_content"])
        elif change["change_type"] == "modified":
            # Восстановить старое содержимое
            if change["old_content"] is not None:
                write_file_content(file_path, change["old_content"])
        
        # Синхронизировать с NextCloud
        from services.sync_service import SyncService
        sync_service = SyncService()
        if sync_service.enabled:
            await sync_service.sync_to_nextcloud()
        
        await callback.message.edit_text(
            f"✅ Изменение #{change_id} откачено.\n"
            f"Файл: {change['file_path']}",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка при откате изменения: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка при откате: {str(e)}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("revert_session_") and not c.data.startswith("confirm_revert_session_"))
async def revert_session_callback(callback: CallbackQuery):
    """Обработка запроса на откат всех изменений сессии"""
    await callback.answer()
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Получить изменения сессии
    changes = await db.get_file_changes(session_id=session_id)
    
    if not changes:
        await callback.message.edit_text(
            f"ℹ️ В сессии #{session_id} нет изменений для отката.",
            reply_markup=None
        )
        return
    
    # Показать подтверждение
    keyboard = get_revert_session_keyboard(session_id)
    await callback.message.edit_text(
        f"⚠️ Вы уверены, что хотите откатить все изменения сессии #{session_id}?\n\n"
        f"Будет откачено {len(changes)} изменений.\n"
        f"Это действие нельзя отменить.",
        reply_markup=keyboard
    )


@router.callback_query(lambda c: c.data.startswith("confirm_revert_session_"))
async def confirm_revert_session_callback(callback: CallbackQuery):
    """Обработка подтверждения отката всех изменений сессии"""
    await callback.answer("⏳ Откатываю изменения...")
    
    try:
        session_id = int(callback.data.split("_")[-1])
    except ValueError:
        await callback.answer("❌ Неверный ID сессии", show_alert=True)
        return
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        await callback.answer("❌ Сессия не найдена", show_alert=True)
        return
    
    # Получить изменения сессии (в обратном порядке для правильного отката)
    changes = await db.get_file_changes(session_id=session_id)
    changes.reverse()  # Откатываем в обратном порядке
    
    reverted_count = 0
    errors = []
    
    for change in changes:
        # file_path в БД хранится как относительный путь от LOCAL_KB_PATH
        file_path = Path(config.LOCAL_KB_PATH) / change["file_path"]
        
        try:
            if change["change_type"] == "created":
                if file_path.exists():
                    file_path.unlink()
                    reverted_count += 1
            elif change["change_type"] == "deleted":
                if change["old_content"]:
                    write_file_content(file_path, change["old_content"])
                    reverted_count += 1
            elif change["change_type"] == "modified":
                if change["old_content"] is not None:
                    write_file_content(file_path, change["old_content"])
                    reverted_count += 1
        except Exception as e:
            logger.error(f"Ошибка при откате изменения #{change['id']}: {e}")
            errors.append(change["file_path"])
    
    # Синхронизировать с NextCloud
    sync_success = False
    try:
        from services.sync_service import SyncService
        sync_service = SyncService()
        if sync_service.enabled:
            sync_success = await sync_service.sync_to_nextcloud()
    except Exception as e:
        logger.error(f"Ошибка при синхронизации после отката: {e}")
    
    response = f"✅ Откат завершен.\n\n"
    response += f"Откачено изменений: {reverted_count} из {len(changes)}\n"
    
    if errors:
        response += f"\n⚠️ Ошибки при откате {len(errors)} файлов:\n"
        for error_file in errors[:5]:
            response += f"  • {error_file}\n"
    
    if sync_success:
        response += "\n✅ Изменения синхронизированы с NextCloud"
    else:
        response += "\n⚠️ Не удалось синхронизировать с NextCloud"
    
    await callback.message.edit_text(response, reply_markup=None)


# Обработчики главного меню
@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Обработка возврата в главное меню"""
    from handlers.keyboards import format_active_session_info
    
    db = await get_db()
    user_id = callback.from_user.id
    is_admin = await db.is_user_admin(user_id)
    
    # Получить активную сессию
    user = await db.ensure_user(user_id, callback.from_user.username)
    active_session = await db.get_active_session(user["id"])
    
    # Сформировать текст меню с информацией об активной сессии
    menu_text = "🏠 <b>Главное меню</b>\n\nВыберите действие:"
    if active_session:
        menu_text += format_active_session_info(active_session)
    
    await callback.answer()
    await callback.message.edit_text(
        menu_text,
        reply_markup=get_main_menu_inline_keyboard_with_admin(
            is_admin=is_admin,
            active_session=active_session
        ),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data == "main_new_query")
async def main_new_query_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Новый запрос' из главного меню"""
    from handlers.commands import new_query_handler
    
    await callback.answer()
    # Создать временное сообщение для обработчика
    fake_message = FakeMessage(callback)
    await new_query_handler(fake_message, state)


@router.callback_query(lambda c: c.data == "main_new_chat")
async def main_new_chat_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Новый чат' из главного меню"""
    from handlers.commands import new_chat_handler
    
    await callback.answer()
    fake_message = FakeMessage(callback)
    await new_chat_handler(fake_message, state)


@router.callback_query(lambda c: c.data == "main_sessions")
async def main_sessions_callback(callback: CallbackQuery):
    """Обработка кнопки 'Мои сессии' из главного меню"""
    await callback.answer()
    
    db = await get_db()
    user_id = callback.from_user.id
    user = await db.ensure_user(user_id, callback.from_user.username)
    
    # Получить сессии для отображения с пагинацией
    page_sessions, active_session_id, total_count = await get_user_sessions_for_display(
        user_id=user["id"],
        page=0,
        per_page=5,
        limit=20
    )
    
    if not page_sessions:
        await callback.message.edit_text(
            "ℹ️ У вас нет сессий.\n\n"
            "Используйте кнопку '📚 Новый запрос' для создания новой сессии.",
            reply_markup=None
        )
        return
    
    # Форматировать список сессий
    response = format_sessions_list(
        sessions=page_sessions,
        active_session_id=active_session_id,
        page=0,
        per_page=5,
        total_count=total_count
    )
    
    # Получить все сессии для клавиатуры (нужны для навигации)
    all_sessions = await db.get_user_sessions(user["id"], limit=20)
    sessions = [s for s in all_sessions if s.get("status") != str(SessionStatus.DELETED)]
    
    keyboard = get_sessions_keyboard(sessions, page=0)
    await callback.message.edit_text(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "main_history")
async def main_history_callback(callback: CallbackQuery):
    """Обработка кнопки 'История' из главного меню"""
    from handlers.commands import history_handler
    
    await callback.answer()
    fake_message = FakeMessage(callback)
    await history_handler(fake_message)


@router.callback_query(lambda c: c.data == "main_sync")
async def main_sync_callback(callback: CallbackQuery):
    """Обработка кнопки 'Синхронизация' из главного меню"""
    from services.sync_service import SyncService
    
    await callback.answer("🔄 Начинаю синхронизацию...")
    
    # Создать сообщение для прогресса
    sync_message = await callback.message.answer("🔄 Синхронизация с NextCloud...")
    
    try:
        sync_service = SyncService()
        
        if not sync_service.enabled:
            await sync_message.edit_text("❌ Синхронизация отключена. Проверьте настройки в .env")
            return
        
        # Callback для обновления прогресса с защитой от флуда
        last_update_time = {}
        
        async def update_progress(stage: str, current: int, total: int):
            """Обновить сообщение с прогрессом синхронизации"""
            stage_names = {
                "upload": "📤 Загрузка в NextCloud",
                "download": "📥 Загрузка из NextCloud"
            }
            stage_name = stage_names.get(stage, "🔄 Синхронизация")
            
            if total > 0:
                percentage = int((current / total) * 100)
            else:
                percentage = 0
            
            # Проверка: обновлять только если прошло минимум 1 секунда с последнего обновления
            now = datetime.now()
            last_time = last_update_time.get(stage)
            
            should_update = False
            if last_time is None:
                should_update = True  # Первое обновление
            elif (now - last_time) >= timedelta(seconds=1):
                should_update = True  # Прошла минимум 1 секунда
            elif current == total:
                should_update = True  # Завершение этапа (всегда обновляем)
            
            if not should_update:
                return
            
            progress_text = f"{stage_name}\n\n"
            progress_text += f"Обработано файлов: {current} из {total}"
            
            if total > 0:
                progress_text += f" ({percentage}%)"
            
            try:
                await sync_message.edit_text(progress_text)
                last_update_time[stage] = now
            except Exception as e:
                error_str = str(e)
                # Обработка Flood control
                if "Flood control" in error_str or "retry after" in error_str.lower():
                    # Извлечь время ожидания из ошибки
                    retry_match = re.search(r'retry after (\d+)', error_str.lower())
                    if retry_match:
                        retry_after = int(retry_match.group(1))
                        logger.warning(f"Flood control: ждем {retry_after} секунд перед следующим обновлением")
                        # Увеличить время последнего обновления, чтобы не обновлять сразу после ожидания
                        last_update_time[stage] = datetime.now() + timedelta(seconds=retry_after)
                        await asyncio.sleep(retry_after)
                    else:
                        # Если не удалось извлечь время, ждем 5 секунд
                        last_update_time[stage] = datetime.now() + timedelta(seconds=5)
                        await asyncio.sleep(5)
                    # Не пытаемся обновить сразу после ожидания - подождем следующего вызова
                else:
                    logger.debug(f"Не удалось обновить сообщение прогресса: {e}")
        
        sync_service.set_progress_callback(update_progress)
        
        # Синхронизировать в обе стороны (сначала из NextCloud, потом в NextCloud)
        await sync_message.edit_text("📥 Загрузка из NextCloud...\n\nПолучение списка файлов...")
        sync_from = await sync_service.sync_from_nextcloud(show_notification=False)
        
        await sync_message.edit_text("📤 Загрузка в NextCloud...\n\nПодготовка...")
        sync_to = await sync_service.sync_to_nextcloud()
        
        # Финальное сообщение
        if sync_to and sync_from:
            await sync_message.edit_text(
                "✅ Синхронизация завершена успешно",
                reply_markup=None
            )
        elif sync_to:
            await sync_message.edit_text(
                "✅ Изменения загружены в NextCloud\n⚠️ Не удалось загрузить изменения из NextCloud",
                reply_markup=None
            )
        elif sync_from:
            await sync_message.edit_text(
                "✅ Изменения загружены из NextCloud\n⚠️ Не удалось загрузить изменения в NextCloud",
                reply_markup=None
            )
        else:
            await sync_message.edit_text(
                "❌ Ошибка при синхронизации. Проверьте логи.",
                reply_markup=None
            )
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        await sync_message.edit_text(
            f"❌ Ошибка при синхронизации: {str(e)}",
            reply_markup=None
        )


@router.callback_query(lambda c: c.data == "main_help")
async def main_help_callback(callback: CallbackQuery):
    """Обработка кнопки 'Помощь' из главного меню"""
    from handlers.commands import help_handler
    
    await callback.answer()
    fake_message = FakeMessage(callback)
    await help_handler(fake_message)


@router.callback_query(lambda c: c.data in ["cancel_revert", "cancel_delete"])
async def cancel_action_callback(callback: CallbackQuery):
    """Обработка отмены действий"""
    await callback.answer("❌ Действие отменено")
    await callback.message.delete()


@router.callback_query(lambda c: c.data == "start_collect_mode")
async def start_collect_mode_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка включения режима сбора сообщений через inline-кнопку"""
    from handlers.commands import collect_mode_handler
    
    # Создать сообщение для обработчика
    fake_message = FakeMessage(callback)
    await collect_mode_handler(fake_message, state)
    await callback.answer("✅ Режим сбора сообщений включен")


@router.callback_query(lambda c: c.data == "transcribe_last_voice")
async def transcribe_last_voice_callback(callback: CallbackQuery):
    """Обработка расшифровки последнего голосового сообщения через inline-кнопку"""
    from handlers.commands import transcribe_handler
    
    # Создать сообщение для обработчика
    fake_message = FakeMessage(callback)
    fake_message.text = "/transcribe"
    fake_message.bot = callback.bot
    await transcribe_handler(fake_message)
    await callback.answer("🎤 Расшифровка начата")


# ========== Обработчики для голосовых в режиме сбора (авто-прикрепление) ==========

@router.callback_query(lambda c: c.data.startswith("voice_show_full_"))
async def voice_show_full_callback(callback: CallbackQuery, state: FSMContext):
    """Показать полную расшифровку голосового сообщения в режиме сбора"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_show_full_", "")
        state_data = await state.get_data()
        voice_ref = state_data.get(f"voice_ref_{voice_id}")
        
        if not voice_ref:
            await callback.message.answer("❌ Данные расшифровки не найдены.")
            return
        
        transcription = voice_ref["transcription"]
        
        # Показать полную расшифровку отдельным сообщением для удобного копирования
        from utils.message_helpers import markdown_to_html
        try:
            html_text = markdown_to_html(transcription)
            await callback.message.answer(
                f"🎤 <b>Полная расшифровка:</b>\n\n{html_text}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await callback.message.answer(
                f"🎤 Полная расшифровка:\n\n{transcription}",
                parse_mode=None
            )
        
    except Exception as e:
        logger.error(f"Ошибка при показе полной расшифровки: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(lambda c: c.data.startswith("voice_correct_"))
async def voice_correct_callback(callback: CallbackQuery, state: FSMContext):
    """Исправить расшифровку голосового — удаляет голосовое из билдера и показывает текст для копирования"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_correct_", "")
        state_data = await state.get_data()
        voice_ref = state_data.get(f"voice_ref_{voice_id}")
        
        if not voice_ref:
            await callback.message.answer("❌ Данные расшифровки не найдены.")
            return
        
        file_id = voice_ref["file_id"]
        transcription = voice_ref["transcription"]
        
        # Удалить голосовое из QueryBuilder
        builder = query_builder_from_state(state_data)
        builder.voice_files = [v for v in builder.voice_files if v.get("file_id") != file_id]
        
        # Сохранить builder и очистить ссылку
        new_state = query_builder_to_state(builder)
        new_state[f"voice_ref_{voice_id}"] = None
        await state.update_data(**new_state)
        
        summary = builder.get_summary()
        
        logger.info(f"Голосовое {file_id} удалено из билдера для исправления. Осталось голосовых: {len(builder.voice_files)}")
        
        # Обновить сообщение — убрать кнопки
        try:
            await callback.message.edit_text(
                f"✏️ Расшифровка удалена из запроса.\n\n{summary}" if summary != "Пусто" else "✏️ Расшифровка удалена из запроса.",
                reply_markup=None,
                parse_mode=None
            )
        except Exception:
            pass
        
        # Показать текст расшифровки для копирования
        await callback.message.answer(
            f"📋 Скопируйте текст, исправьте и отправьте как сообщение:\n\n{transcription}",
            parse_mode=None
        )
        
    except Exception as e:
        logger.error(f"Ошибка при исправлении расшифровки: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ========== Обработчики выбора действия с голосовым сообщением (обычный режим) ==========

@router.callback_query(lambda c: c.data.startswith("voice_add_to_collect_"))
async def voice_add_to_collect_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка добавления голосового к запросу в режиме сбора"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_add_to_collect_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Получить данные
        audio_path = Path(voice_data["audio_path"])
        transcribed_text = voice_data["transcribed_text"]
        file_id = voice_data["file_id"]
        
        # Добавить в QueryBuilder
        builder = query_builder_from_state(state_data) if (state_data.get("text_parts") or state_data.get("voice_files") or state_data.get("media_files")) else QueryBuilder()
        builder.add_voice(file_id, audio_path, transcribed_text)
        
        # Сохранить обратно в состояние и удалить временные данные голосового за один вызов
        new_state = query_builder_to_state(builder)
        new_state[f"voice_{voice_id}"] = None  # Пометить временные данные как удалённые
        await state.update_data(**new_state)
        
        # Показать информацию
        summary = builder.get_summary()
        transcription_preview = transcribed_text[:100] + "..." if len(transcribed_text) > 100 else transcribed_text
        
        from handlers.keyboards import get_collecting_messages_keyboard
        await callback.message.answer(
            f"✅ Голосовое сообщение добавлено к запросу.\n\n"
            f"📝 Расшифровка: {transcription_preview}\n\n"
            f"{summary}\n\n"
            f"Продолжайте добавлять сообщения или нажмите '✅ Завершить сбор' для отправки.",
            reply_markup=get_collecting_messages_keyboard(),
            parse_mode=None
        )
        
        # Удалить сообщение с кнопками
        try:
            await callback.message.delete()
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении голосового к запросу: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(lambda c: c.data.startswith("voice_transcribe_only_"))
async def voice_transcribe_only_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка только транскрибации голосового (без запроса к БЗ)"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_transcribe_only_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Получить данные
        transcribed_text = voice_data["transcribed_text"]
        language = voice_data.get("language", "unknown")
        audio_path = Path(voice_data["audio_path"])
        
        # Удалить временные данные голосового (не перезаписывая остальное состояние)
        await state.update_data(**{f"voice_{voice_id}": None})
        
        # Показать расшифровку
        from utils.message_helpers import markdown_to_html
        html_text = markdown_to_html(transcribed_text)
        response = f"🎤 <b>Расшифровка:</b>\n\n{html_text}"
        if language and language != "unknown":
            response += f"\n\n🌐 Язык: {language}"
        
        await callback.message.answer(response, parse_mode=ParseMode.HTML)
        
        # Удалить временный файл
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")
        
        # Удалить сообщение с кнопками
        try:
            await callback.message.delete()
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"Ошибка при транскрибации голосового: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(lambda c: c.data.startswith("voice_send_query_"))
async def voice_send_query_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка отправки голосового как запроса к БЗ"""
    await callback.answer("📤 Отправляю запрос...")
    
    try:
        voice_id = callback.data.replace("voice_send_query_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Получить данные
        transcribed_text = voice_data["transcribed_text"]
        audio_path = Path(voice_data["audio_path"])
        file_id = voice_data["file_id"]
        file_size = voice_data.get("file_size")
        
        # Получить или создать сессию
        user_id = callback.from_user.id
        session_service = SessionService()
        active_session = await session_service.get_or_create_active_session(
            user_id=user_id,
            username=callback.from_user.username,
            session_type=SessionType.QUERY_WITH_KB
        )
        session_id = active_session["id"]
        
        # Сохранить сообщение пользователя с транскрипцией
        db = await get_db()
        message_obj = await db.add_message(session_id, str(MessageRole.USER), transcribed_text)
        
        # Сохранить вложение в БД
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=message_obj["id"],
            file_type="voice",
            file_id=file_id,
            file_path=str(audio_path),
            file_name=f"{file_id}.ogg",
            file_size=file_size
        )
        
        # Сохранить транскрипцию в БД
        await db.add_transcription(
            attachment_id=attachment["id"],
            text=transcribed_text,
            language=voice_data.get("language", "unknown")
        )
        
        # Удалить временные данные голосового (не перезаписывая остальное состояние)
        await state.update_data(**{f"voice_{voice_id}": None})
        
        # Удалить сообщение с кнопками
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Обработать транскрибированный текст как запрос
        query_service = QueryProcessingService()
        fake_message = FakeMessage(callback)
        await query_service.process_query(
            query=transcribed_text,
            session_id=session_id,
            message=fake_message,
            save_user_message=False  # Сообщение уже сохранено выше
        )
        
        # Удалить временный файл
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса из голосового: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(lambda c: c.data.startswith("voice_use_as_prompt_"))
async def voice_use_as_prompt_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка использования голосового как prompt - спрашиваем про режим сбора"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_use_as_prompt_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Показать вопрос про режим сбора
        from handlers.keyboards import get_enable_collect_mode_keyboard
        await callback.message.edit_text(
            "❓ Включить режим сбора сообщений для этого prompt?",
            reply_markup=get_enable_collect_mode_keyboard(voice_id)
        )
        
    except Exception as e:
        logger.error(f"Ошибка при использовании голосового как prompt: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(lambda c: c.data.startswith("voice_prompt_enable_collect_"))
async def voice_prompt_enable_collect_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка использования голосового как prompt с включением режима сбора"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_prompt_enable_collect_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Получить данные
        audio_path = Path(voice_data["audio_path"])
        transcribed_text = voice_data["transcribed_text"]
        file_id = voice_data["file_id"]
        
        # Включить режим сбора
        from handlers.states import QueryStates
        await state.set_state(QueryStates.collecting_messages)
        
        # Инициализировать QueryBuilder с транскрипцией (только через add_voice, без дублирования в text_parts)
        builder = QueryBuilder()
        builder.add_voice(file_id, audio_path, transcribed_text)
        
        # Сохранить в состояние и удалить временные данные голосового за один вызов
        new_state = query_builder_to_state(builder)
        new_state[f"voice_{voice_id}"] = None  # Пометить временные данные как удалённые
        await state.update_data(**new_state)
        
        # Показать информацию
        from handlers.keyboards import get_collecting_messages_keyboard
        summary = builder.get_summary()
        
        # edit_text принимает только InlineKeyboardMarkup, поэтому убираем кнопки
        await callback.message.edit_text(
            f"✅ Режим сбора сообщений включен.\n\n"
            f"📝 Prompt добавлен: {transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}\n\n"
            f"{summary}\n\n"
            f"Продолжайте добавлять сообщения или нажмите '✅ Завершить сбор' для отправки.",
            reply_markup=None,
            parse_mode=None
        )
        
        # Отправить reply-клавиатуру отдельным сообщением
        await callback.message.answer(
            "Готовы отправить запрос?",
            reply_markup=get_collecting_messages_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при включении режима сбора с prompt: {e}", exc_info=True)
        try:
            await callback.message.answer(f"❌ Ошибка: {str(e)}", parse_mode=None)
        except Exception:
            pass


@router.callback_query(lambda c: c.data.startswith("voice_prompt_no_collect_"))
async def voice_prompt_no_collect_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка использования голосового как prompt без режима сбора"""
    await callback.answer()
    
    try:
        voice_id = callback.data.replace("voice_prompt_no_collect_", "")
        state_data = await state.get_data()
        voice_data = state_data.get(f"voice_{voice_id}")
        
        if not voice_data:
            await callback.message.answer("❌ Данные голосового сообщения не найдены.")
            return
        
        # Получить данные
        transcribed_text = voice_data["transcribed_text"]
        audio_path = Path(voice_data["audio_path"])
        file_id = voice_data["file_id"]
        file_size = voice_data.get("file_size")
        
        # Получить или создать сессию
        user_id = callback.from_user.id
        session_service = SessionService()
        active_session = await session_service.get_or_create_active_session(
            user_id=user_id,
            username=callback.from_user.username,
            session_type=SessionType.QUERY_WITH_KB
        )
        session_id = active_session["id"]
        
        # Сохранить сообщение пользователя с транскрипцией
        db = await get_db()
        message_obj = await db.add_message(session_id, str(MessageRole.USER), transcribed_text)
        
        # Сохранить вложение в БД
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=message_obj["id"],
            file_type="voice",
            file_id=file_id,
            file_path=str(audio_path),
            file_name=f"{file_id}.ogg",
            file_size=file_size
        )
        
        # Сохранить транскрипцию в БД
        await db.add_transcription(
            attachment_id=attachment["id"],
            text=transcribed_text,
            language=voice_data.get("language", "unknown")
        )
        
        # Удалить временные данные голосового (не перезаписывая остальное состояние)
        await state.update_data(**{f"voice_{voice_id}": None})
        
        # Удалить сообщение с кнопками
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Обработать транскрибированный текст как запрос
        query_service = QueryProcessingService()
        fake_message = FakeMessage(callback)
        await query_service.process_query(
            query=transcribed_text,
            session_id=session_id,
            message=fake_message,
            save_user_message=False  # Сообщение уже сохранено выше
        )
        
        # Удалить временный файл
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка при использовании голосового как prompt: {e}", exc_info=True)
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ========== Административные обработчики ==========

@router.callback_query(lambda c: c.data == "admin_menu")
@require_admin
async def admin_menu_callback(callback: CallbackQuery):
    """Обработка открытия меню администратора"""
    await callback.answer()
    await callback.message.edit_text(
        "⚙️ <b>Меню администратора</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data == "admin_list_users")
@require_admin
async def admin_list_users_callback(callback: CallbackQuery):
    """Показать список разрешенных пользователей"""
    db = await get_db()
    
    try:
        allowed_users = await db.get_allowed_users()
        
        if not allowed_users:
            await callback.answer("ℹ️ Нет разрешенных пользователей", show_alert=True)
            return
        
        response = "👥 <b>Список разрешенных пользователей:</b>\n\n"
        for user in allowed_users[:10]:  # Показать первые 10
            admin_marker = "👑" if user.get("is_admin") else ""
            username = user.get("username") or "без username"
            response += f"{admin_marker} <b>{user['telegram_id']}</b> (@{username})\n"
        
        if len(allowed_users) > 10:
            response += f"\n<i>Показано 10 из {len(allowed_users)} пользователей</i>"
        
        await callback.answer()
        await callback.message.edit_text(
            response,
            reply_markup=get_admin_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await send_error_message(
            event=callback,
            error=e,
            user_message=f"❌ Ошибка: {str(e)}",
            log_message="Ошибка при получении списка пользователей"
        )
        await callback.answer(f"❌ Ошибка: {str(e)}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("admin_allow_start"))
@require_admin
async def admin_allow_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начать процесс разрешения доступа"""
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_contact)
    await state.update_data(admin_action="allow")
    
    reply_kb, inline_kb = get_admin_contact_request_keyboard("allow")
    
    await callback.message.edit_text(
        "✅ <b>Разрешить доступ пользователю</b>\n\n"
        "Выберите способ:\n\n"
        "• Нажмите кнопку '👤 Выбрать пользователя' для выбора через UI Telegram\n"
        "• Или используйте кнопки ниже для других способов",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML
    )
    # Отправить reply-клавиатуру отдельным сообщением
    await callback.message.answer(
        "👤 Нажмите кнопку ниже для выбора пользователя:",
        reply_markup=reply_kb
    )


@router.callback_query(lambda c: c.data.startswith("admin_disallow_start"))
@require_admin
async def admin_disallow_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начать процесс запрета доступа"""
    db = await get_db()
    await callback.answer()
    
    # Получить список разрешенных пользователей для выбора
    allowed_users = await db.get_allowed_users()
    
    if not allowed_users:
        await callback.message.edit_text(
            "ℹ️ Нет разрешенных пользователей для запрета доступа.",
            reply_markup=get_admin_menu_keyboard()
        )
        return
    
    await state.set_state(AdminStates.waiting_for_user_selection)
    await state.update_data(admin_action="disallow")
    
    await callback.message.edit_text(
        "❌ <b>Запретить доступ пользователю</b>\n\n"
        "Выберите пользователя из списка:",
        reply_markup=get_users_selection_keyboard(allowed_users, "disallow", page=0),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data.startswith("admin_set_admin_start"))
@require_admin
async def admin_set_admin_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начать процесс назначения администратора"""
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_contact)
    await state.update_data(admin_action="set_admin")
    
    reply_kb, inline_kb = get_admin_contact_request_keyboard("set_admin")
    
    await callback.message.edit_text(
        "👑 <b>Назначить администратора</b>\n\n"
        "Выберите способ:\n\n"
        "• Нажмите кнопку '👤 Выбрать пользователя' для выбора через UI Telegram\n"
        "• Или используйте кнопки ниже для других способов",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML
    )
    # Отправить reply-клавиатуру отдельным сообщением
    await callback.message.answer(
        "👤 Нажмите кнопку ниже для выбора пользователя:",
        reply_markup=reply_kb
    )


@router.callback_query(lambda c: c.data.startswith("admin_remove_admin_start"))
@require_admin
async def admin_remove_admin_start_callback(callback: CallbackQuery, state: FSMContext):
    """Начать процесс удаления прав администратора"""
    db = await get_db()
    await callback.answer()
    
    # Получить список администраторов
    allowed_users = await db.get_allowed_users()
    admin_users = [u for u in allowed_users if u.get("is_admin")]
    
    if not admin_users:
        await callback.message.edit_text(
            "ℹ️ Нет других администраторов.",
            reply_markup=get_admin_menu_keyboard()
        )
        return
    
    await state.set_state(AdminStates.waiting_for_user_selection)
    await state.update_data(admin_action="remove_admin")
    
    await callback.message.edit_text(
        "🔻 <b>Убрать права администратора</b>\n\n"
        "Выберите администратора из списка:",
        reply_markup=get_users_selection_keyboard(admin_users, "remove_admin", page=0),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data.startswith("admin_select_user_"))
@require_admin
async def admin_select_user_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора пользователя из списка"""
    db = await get_db()
    user_id = callback.from_user.id
    
    # Извлечь действие и telegram_id из callback_data
    # Формат: admin_select_user_{action}_{telegram_id}
    # Проблема: remove_admin содержит подчеркивание, поэтому нужно парсить по-другому
    prefix = "admin_select_user_"
    if not callback.data.startswith(prefix):
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    # Убрать префикс и разбить оставшуюся часть
    data_without_prefix = callback.data[len(prefix):]
    # Разделить на действие и ID (ID всегда последний элемент после последнего подчеркивания)
    parts = data_without_prefix.rsplit("_", 1)  # Разделить только по последнему подчеркиванию
    
    if len(parts) != 2:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    action = parts[0]  # allow, disallow, set_admin, remove_admin
    try:
        target_telegram_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Неверный ID пользователя", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        if action == "allow":
            await db.allow_user(target_telegram_id)
            await db.ensure_user(target_telegram_id)  # Создать пользователя если его нет
            result_text = f"✅ Пользователю {target_telegram_id} разрешен доступ."
            logger.info(f"Администратор {user_id} разрешил доступ пользователю {target_telegram_id}")
        elif action == "disallow":
            await db.disallow_user(target_telegram_id)
            result_text = f"❌ Пользователю {target_telegram_id} запрещен доступ."
            logger.info(f"Администратор {user_id} запретил доступ пользователю {target_telegram_id}")
        elif action == "set_admin":
            await db.set_user_admin(target_telegram_id, is_admin=True)
            result_text = f"👑 Пользователю {target_telegram_id} назначены права администратора."
            logger.info(f"Администратор {user_id} назначил администратором пользователя {target_telegram_id}")
        elif action == "remove_admin":
            await db.set_user_admin(target_telegram_id, is_admin=False)
            result_text = f"🔻 У пользователя {target_telegram_id} убраны права администратора."
            logger.info(f"Администратор {user_id} убрал права администратора у пользователя {target_telegram_id}")
        else:
            await callback.message.edit_text("❌ Неизвестное действие.", reply_markup=get_admin_menu_keyboard())
            return
        
        await state.clear()
        await callback.message.edit_text(
            result_text,
            reply_markup=get_admin_menu_keyboard()
        )
    except Exception as e:
        from handlers.keyboards import get_admin_menu_keyboard
        await send_error_message(
            event=callback,
            error=e,
            user_message=f"❌ Ошибка: {str(e)}",
            log_message="Ошибка при выполнении административного действия",
            reply_markup=get_admin_menu_keyboard()
        )


@router.callback_query(lambda c: c.data.startswith("admin_users_page_"))
@require_admin
async def admin_users_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка пагинации списка пользователей"""
    db = await get_db()
    
    # Формат: admin_users_page_{action}_{page}
    parts = callback.data.split("_")
    if len(parts) < 5:
        await callback.answer("❌ Ошибка формата", show_alert=True)
        return
    
    action = parts[3]
    try:
        page = int(parts[4])
    except ValueError:
        await callback.answer("❌ Неверный номер страницы", show_alert=True)
        return
    
    await callback.answer()
    
    # Получить список пользователей в зависимости от действия
    if action == "disallow":
        users = await db.get_allowed_users()
    elif action == "remove_admin":
        all_users = await db.get_allowed_users()
        users = [u for u in all_users if u.get("is_admin")]
    else:
        users = await db.get_allowed_users()
    
    if not users:
        await callback.message.edit_text(
            "ℹ️ Нет пользователей для выбора.",
            reply_markup=get_admin_menu_keyboard()
        )
        return
    
    action_labels = {
        "disallow": "❌ Запретить доступ пользователю",
        "remove_admin": "🔻 Убрать права администратора"
    }
    
    await callback.message.edit_text(
        f"{action_labels.get(action, 'Выбор пользователя')}\n\n"
        "Выберите пользователя из списка:",
        reply_markup=get_users_selection_keyboard(users, action, page=page),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data.startswith("admin_manual_id_"))
@require_admin
async def admin_manual_id_callback(callback: CallbackQuery, state: FSMContext):
    """Переключиться на ручной ввод ID пользователя"""
    db = await get_db()
    
    # Формат: admin_manual_id_{action}
    action = callback.data.split("_")[-1]
    
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_user_contact)
    await state.update_data(admin_action=action)
    
    action_labels = {
        "allow": "✅ Разрешить доступ пользователю",
        "set_admin": "👑 Назначить администратора"
    }
    
    await callback.message.edit_text(
        f"{action_labels.get(action, 'Выбор пользователя')}\n\n"
        "Отправьте Telegram ID пользователя (число):",
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(lambda c: c.data.startswith("admin_list_for_"))
@require_admin
async def admin_list_for_callback(callback: CallbackQuery, state: FSMContext):
    """Показать список всех пользователей для выбора"""
    db = await get_db()
    
    # Формат: admin_list_for_{action}
    action = callback.data.split("_")[-1]
    
    await callback.answer()
    
    # Получить всех пользователей (не только разрешенных)
    # Для этого нужно получить всех пользователей из БД
    # Пока используем get_allowed_users, но можно расширить для получения всех
    users = await db.get_allowed_users()
    
    if not users:
        await callback.message.edit_text(
            "ℹ️ Нет пользователей в базе.",
            reply_markup=get_admin_menu_keyboard()
        )
        return
    
    await state.set_state(AdminStates.waiting_for_user_selection)
    await state.update_data(admin_action=action)
    
    action_labels = {
        "allow": "✅ Разрешить доступ пользователю",
        "set_admin": "👑 Назначить администратора"
    }
    
    await callback.message.edit_text(
        f"{action_labels.get(action, 'Выбор пользователя')}\n\n"
        "Выберите пользователя из списка:",
        reply_markup=get_users_selection_keyboard(users, action, page=0),
        parse_mode=ParseMode.HTML
    )

