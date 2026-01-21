"""
Обработчики команд бота
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, Contact
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from utils.db_helpers import get_db
from handlers.states import QueryStates, AdminStates
from handlers.keyboards import (
    get_confirm_query_keyboard, get_main_keyboard, get_new_query_keyboard,
    get_active_session_keyboard, get_collecting_messages_keyboard,
    get_admin_menu_keyboard, get_cancel_keyboard
)
from utils.query_builder import QueryBuilder, query_builder_to_state

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    from handlers.keyboards import get_main_menu_inline_keyboard_with_admin
    from config import config
    
    db = await get_db()
    user_id = message.from_user.id
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Проверка доступа в режиме restricted
    if config.ACCESS_MODE == "restricted":
        is_allowed = await db.is_user_allowed(user_id)
        if not is_allowed:
            await message.answer(
                "❌ У вас нет доступа к этому боту.\n\n"
                "Обратитесь к администратору для получения доступа."
            )
            logger.warning(
                f"Попытка доступа от неавторизованного пользователя при /start: "
                f"telegram_id={user_id}, username={message.from_user.username}"
            )
            return
    
    # Проверить, является ли пользователь администратором
    is_admin = await db.is_user_admin(user_id)
    
    await message.answer(
        "👋 Привет! Я бот для работы с базой знаний.\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=get_main_keyboard()
    )
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_inline_keyboard_with_admin(is_admin=is_admin),
        parse_mode=ParseMode.HTML
    )


@router.message(Command("help"))
async def help_handler(message: Message):
    """Обработчик команды /help"""
    from handlers.keyboards import get_main_menu_inline_keyboard_with_admin
    from utils.db_helpers import get_db
    
    db = await get_db()
    user_id = message.from_user.id
    is_admin = await db.is_user_admin(user_id)
    
    help_text = """📚 <b>Справка по использованию бота</b>

<b>🏠 Главное меню:</b>
Используйте кнопку "🏠 Главное меню" под сообщением, чтобы открыть главное меню со всеми доступными действиями.

<b>📋 Основные действия:</b>
• 📚 Новый запрос - Начать новый запрос с контекстом базы знаний
• 💬 Новый чат - Начать пустой чат (без контекста)
• 📋 Мои сессии - Показать список ваших сессий
• 📜 История - Показать историю изменений текущей сессии
• 🔄 Синхронизация - Принудительная синхронизация с NextCloud

<b>💡 Работа с сессиями:</b>
• Нажмите на сессию в списке, чтобы увидеть детали и доступные действия
• Вы можете переключиться на другую сессию, просмотреть детали, завершить или удалить сессию
• Активная сессия отмечена зелёным индикатором 🟢

<b>📝 Режим сбора сообщений:</b>
• При создании нового запроса доступна кнопка "Режим сбора сообщений"
• В этом режиме можно отправить несколько сообщений (текст, голос, файлы) перед отправкой запроса
• Все сообщения будут собраны вместе и отправлены одним запросом
• Используйте кнопку "✅ Завершить сбор" для отправки или "❌ Отмена" для отмены

<b>🎤 Голосовые сообщения:</b>
• Отправляйте голосовые сообщения - они автоматически расшифруются
• После расшифровки доступна кнопка для повторной расшифровки при необходимости

<b>📄 История изменений:</b>
• Просматривайте историю изменений файлов в текущей сессии
• Откатывайте отдельные изменения или все изменения сессии через кнопки"""
    
    await message.answer(help_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())
    await message.answer(
        "🏠 <b>Главное меню</b>\n\nВыберите действие:",
        reply_markup=get_main_menu_inline_keyboard_with_admin(is_admin=is_admin),
        parse_mode=ParseMode.HTML
    )


@router.message(Command("new_query"))
async def new_query_handler(message: Message, state: FSMContext):
    """Начать новый запрос с контекстом базы знаний"""
    db = await get_db()
    user_id = message.from_user.id
    
    # Создать или обновить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Деактивировать предыдущую активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session:
        await db.update_session(active_session["id"], status="completed")
    
    # Создать новую сессию с контекстом базы знаний
    session = await db.create_session(
        user_id=user["id"],
        session_type="query_with_kb",
        status="active"
    )
    
    # Сохранить ID сессии в состоянии
    await state.update_data(session_id=session["id"])
    
    # Очистить режим сбора сообщений (если был активен)
    await state.set_state(None)
    
    reply_kb, inline_kb = get_new_query_keyboard()
    await message.answer(
        f"✅ Начат новый запрос с контекстом базы знаний.\n"
        f"Сессия #{session['id']}\n\n"
        f"Отправьте ваш вопрос текстом, голосом или с файлами.\n\n"
        f"Вы можете включить режим сбора сообщений, чтобы отправить несколько сообщений одним запросом.",
        reply_markup=reply_kb,
        reply_to_message_id=None
    )
    # Отправить отдельное сообщение с inline-кнопкой
    await message.answer(
        "💡 <b>Совет:</b> Используйте режим сбора сообщений для отправки нескольких сообщений одним запросом.",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML
    )


@router.message(Command("collect"))
async def collect_mode_handler(message: Message, state: FSMContext):
    """Включить режим сбора сообщений"""
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
    
    # Включить режим сбора сообщений
    await state.set_state(QueryStates.collecting_messages)
    
    # Инициализировать пустой QueryBuilder
    builder = QueryBuilder()
    await state.update_data(**query_builder_to_state(builder))
    
    try:
        await message.answer(
            "📝 Режим сбора сообщений включен.\n\n"
            "Теперь вы можете отправлять несколько сообщений:\n"
            "- Текстовые сообщения\n"
            "- Голосовые сообщения\n"
            "- Файлы и фото\n\n"
            "Все сообщения будут собраны вместе. "
            "Когда будете готовы, нажмите кнопку '✅ Завершить сбор' или используйте кнопку ниже.",
            reply_markup=get_collecting_messages_keyboard()
        )
        await message.answer(
            "Готовы отправить запрос?",
            reply_markup=get_confirm_query_keyboard()
        )
    except TelegramBadRequest as e:
        logger.error(f"Ошибка при отправке сообщения с клавиатурой: {e}")
        # Попробовать отправить без клавиатуры
        try:
            await message.answer(
                "📝 Режим сбора сообщений включен.\n\n"
                "Теперь вы можете отправлять несколько сообщений:\n"
                "- Текстовые сообщения\n"
                "- Голосовые сообщения\n"
                "- Файлы и фото\n\n"
                "Все сообщения будут собраны вместе.\n\n"
                "Используйте кнопку '✅ Завершить сбор' для отправки запроса.",
                reply_markup=get_collecting_messages_keyboard()
            )
            logger.warning("Сообщение отправлено без клавиатуры из-за ошибки Telegram API")
        except Exception as e2:
            logger.error(f"Критическая ошибка при отправке сообщения: {e2}")
            await message.answer("✅ Режим сбора сообщений включен.")


@router.message(Command("stop_collect"))
async def stop_collect_mode_handler(message: Message, state: FSMContext):
    """Отключить режим сбора сообщений"""
    current_state = await state.get_state()
    
    if current_state != QueryStates.collecting_messages.state:
        await message.answer(
            "ℹ️ Режим сбора сообщений не активен.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Очистить состояние
    await state.clear()
    
    await message.answer(
        "❌ Режим сбора сообщений отключен.\n"
        "Все собранные данные удалены.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("new_chat"))
async def new_chat_handler(message: Message, state: FSMContext):
    """Начать пустой чат (без контекста базы знаний)"""
    db = await get_db()
    user_id = message.from_user.id
    
    # Создать или обновить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Деактивировать предыдущую активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session:
        await db.update_session(active_session["id"], status="completed")
    
    # Создать новую сессию без контекста базы знаний
    session = await db.create_session(
        user_id=user["id"],
        session_type="empty_chat",
        status="active"
    )
    
    # Сохранить ID сессии в состоянии
    await state.update_data(session_id=session["id"])
    
    reply_kb, inline_kb = get_new_query_keyboard()
    await message.answer(
        f"✅ Начат новый чат без контекста базы знаний.\n"
        f"Сессия #{session['id']}\n\n"
        f"Отправьте ваш вопрос текстом, голосом или с файлами.",
        reply_markup=reply_kb
    )
    await message.answer(
        "💡 <b>Совет:</b> Используйте режим сбора сообщений для отправки нескольких сообщений одним запросом.",
        reply_markup=inline_kb,
        parse_mode=ParseMode.HTML
    )


@router.message(Command("end_query"))
async def end_query_handler(message: Message, state: FSMContext):
    """Завершить текущий запрос"""
    db = await get_db()
    user_id = message.from_user.id
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session:
        await db.update_session(active_session["id"], status="completed")
        await state.update_data(session_id=None)
        await message.answer(
            f"✅ Сессия #{active_session['id']} завершена.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ Нет активной сессии для завершения.",
            reply_markup=get_main_keyboard()
        )


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Отменить текущую операцию"""
    await state.clear()
    await message.answer(
        "❌ Операция отменена.",
        reply_markup=get_main_keyboard()
    )


@router.message(Command("transcribe"))
async def transcribe_handler(message: Message):
    """Расшифровать последнее голосовое сообщение"""
    from pathlib import Path
    from services.transcription_service import TranscriptionService
    from services.openai_service import OpenAIService
    from utils.file_helpers import download_telegram_file
    from utils.message_helpers import markdown_to_html
    
    user_id = message.from_user.id
    db = await get_db()
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить последнее голосовое сообщение
    last_voice = await db.get_last_voice_attachment(user["id"])
    
    if not last_voice:
        await message.answer(
            "ℹ️ У вас нет голосовых сообщений для расшифровки.\n\n"
            "Отправьте голосовое сообщение, и я его расшифрую."
        )
        return
    
    # Проверить, есть ли уже транскрипция
    existing_transcription = await db.get_transcription(last_voice["id"])
    
    if existing_transcription:
        # Показать существующую транскрипцию
        transcription_text = existing_transcription["text"]
        language = existing_transcription.get("language", "unknown")
        
        response = f"🎤 <b>Расшифровка последнего голосового сообщения:</b>\n\n{markdown_to_html(transcription_text)}"
        if language and language != "unknown":
            response += f"\n\n🌐 Язык: {language}"
        
        await message.answer(response, parse_mode=ParseMode.HTML)
        return
    
    # Если транскрипции нет, нужно расшифровать
    processing_message = await message.answer("🔄 Расшифровываю последнее голосовое сообщение...")
    
    try:
        # Скачать файл, если его нет локально
        if last_voice.get("file_path") and Path(last_voice["file_path"]).exists():
            audio_path = Path(last_voice["file_path"])
        else:
            await processing_message.edit_text("📥 Скачиваю голосовое сообщение...")
            audio_path = await download_telegram_file(message.bot, last_voice["file_id"])
            if not audio_path:
                await processing_message.edit_text("❌ Не удалось скачать голосовое сообщение.")
                return
        
        await processing_message.edit_text("🎙️ Расшифровываю голосовое сообщение...")
        
        # Транскрибировать
        openai_service = OpenAIService()
        transcription_service = TranscriptionService(openai_service)
        
        transcription_result = await transcription_service.transcribe(str(audio_path))
        transcribed_text = transcription_result.get("text", "")
        language = transcription_result.get("language", "unknown")
        
        if not transcribed_text:
            await processing_message.edit_text("❌ Не удалось расшифровать голосовое сообщение.")
            return
        
        # Сохранить транскрипцию в БД
        await db.add_transcription(
            attachment_id=last_voice["id"],
            text=transcribed_text,
            language=language
        )
        
        # Отправить расшифровку
        response = f"🎤 <b>Расшифровка последнего голосового сообщения:</b>\n\n{markdown_to_html(transcribed_text)}"
        if language and language != "unknown":
            response += f"\n\n🌐 Язык: {language}"
        
        await processing_message.edit_text(response, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        logger.error(f"Ошибка при расшифровке голосового сообщения: {e}", exc_info=True)
        await processing_message.edit_text(
            f"❌ Произошла ошибка при расшифровке: {str(e)}"
        )


@router.message(Command("sessions"))
async def sessions_handler(message: Message):
    """Показать список сессий пользователя"""
    from handlers.keyboards import get_sessions_keyboard
    
    db = await get_db()
    user_id = message.from_user.id
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить все сессии пользователя (последние 20 для пагинации)
    all_sessions = await db.get_user_sessions(user["id"], limit=20)
    
    # Исключить удаленные сессии
    sessions = [s for s in all_sessions if s.get("status") != "deleted"]
    
    if not sessions:
        response = "ℹ️ У вас нет сессий.\n\n"
        response += "Используйте кнопку '📚 Новый запрос' для создания новой сессии."
        await message.answer(
            response,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard()
        )
        return
    
    # Найти активную сессию
    active_session = await db.get_active_session(user["id"])
    active_session_id = active_session["id"] if active_session else None
    
    # Форматировать список сессий для первой страницы
    response = "📋 <b>Ваши сессии:</b>\n\n"
    response += "Нажмите на сессию, чтобы увидеть детали и действия.\n\n"
    
    for session in sessions[:5]:  # Показать первые 5
        session_type_emoji = "📚" if session["session_type"] == "query_with_kb" else "💬"
        status_emoji = "🟢" if session["id"] == active_session_id else "⚪"
        session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
        
        messages_count = len(await db.get_session_messages(session["id"]))
        
        response += f"{session_type_emoji} <b>#{session['id']}</b> {status_emoji}\n"
        response += f"  {session_type_label} • {messages_count} сообщений\n\n"
    
    if len(sessions) > 5:
        response += f"\n<i>Показано 5 из {len(sessions)} сессий. Используйте кнопки для навигации.</i>"
    
    keyboard = get_sessions_keyboard(sessions, page=0)
    await message.answer(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.message(Command("switch_session"))
async def switch_session_handler(message: Message, state: FSMContext):
    """Переключиться на другую сессию"""
    db = await get_db()
    user_id = message.from_user.id
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить ID сессии из команды
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("❌ Укажите ID сессии: /switch_session &lt;id&gt;", parse_mode=ParseMode.HTML)
        return
    
    try:
        session_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат ID сессии. Используйте число.")
        return
    
    # Получить сессию
    session = await db.get_session(session_id)
    if not session:
        await message.answer(f"❌ Сессия #{session_id} не найдена.")
        return
    
    # Проверить, что сессия принадлежит пользователю
    if session["user_id"] != user["id"]:
        await message.answer("❌ Эта сессия не принадлежит вам.")
        return
    
    # Деактивировать текущую активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session and active_session["id"] != session_id:
        await db.update_session(active_session["id"], status="completed")
    
    # Активировать выбранную сессию
    await db.update_session(session_id, status="active")
    await state.update_data(session_id=session_id)
    
    messages_count = len(await db.get_session_messages(session_id))
    session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
    
    await message.answer(
        f"✅ Переключено на сессию #{session_id}\n"
        f"Тип: {session_type_label}\n"
        f"Сообщений: {messages_count}",
        reply_markup=get_active_session_keyboard()
    )


@router.message(Command("history"))
async def history_handler(message: Message):
    """Показать историю изменений текущей сессии"""
    from handlers.keyboards import get_history_keyboard
    
    db = await get_db()
    user_id = message.from_user.id
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить активную сессию
    active_session = await db.get_active_session(user["id"])
    
    if not active_session:
        await message.answer(
            "ℹ️ У вас нет активной сессии.\n\n"
            "Используйте кнопку '📚 Новый запрос' для создания новой сессии.",
            reply_markup=get_main_keyboard()
        )
        return
    
    session_id = active_session["id"]
    
    # Получить изменения сессии
    changes = await db.get_file_changes(session_id=session_id)
    
    if not changes:
        await message.answer(
            f"📜 История изменений сессии #{session_id}\n\n"
            "ℹ️ В этой сессии пока нет изменений файлов.",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Форматировать историю для первой страницы
    response = f"📜 <b>История изменений сессии #{session_id}</b>\n\n"
    
    change_type_labels = {
        "created": "➕ Создан",
        "modified": "✏️ Изменен",
        "deleted": "🗑 Удален"
    }
    
    for change in changes[:5]:  # Показать первые 5
        change_type_label = change_type_labels.get(change["change_type"], "📄 Изменен")
        file_name = change["file_path"].split("/")[-1]
        created_at = change["created_at"]
        
        response += f"<b>{file_name}</b> - {change_type_label}\n"
        response += f"  Время: {created_at}\n\n"
    
    if len(changes) > 5:
        response += f"\n<i>Показано 5 из {len(changes)} изменений. Используйте кнопки для навигации.</i>"
    
    keyboard = get_history_keyboard(changes, session_id, page=0)
    await message.answer(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


@router.message(Command("revert"))
async def revert_handler(message: Message):
    """Откатить конкретное изменение"""
    # TODO: Реализовать откат
    await message.answer("↩️ Функция отката будет реализована позже.")


@router.message(Command("revert_session"))
async def revert_session_handler(message: Message):
    """Откатить все изменения текущей сессии"""
    # TODO: Реализовать откат сессии
    await message.answer("↩️ Функция отката сессии будет реализована позже.")


# Старые административные команды удалены - теперь используется интерактивный режим через callbacks


@router.message(AdminStates.waiting_for_user_contact)
async def admin_users_requested_handler(message: Message, state: FSMContext):
    """Обработка выбора пользователя через UI Telegram (кнопка 'Выбрать пользователя')"""
    db = await get_db()
    user_id = message.from_user.id
    
    if not await db.is_user_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.")
        await state.clear()
        return
    
    # Логирование для отладки - проверим все возможные поля
    logger.debug(f"Получено сообщение в состоянии waiting_for_user_contact:")
    logger.debug(f"  text={message.text}")
    logger.debug(f"  contact={message.contact}")
    logger.debug(f"  message_id={message.message_id}")
    logger.debug(f"  from_user={message.from_user}")
    
    # Проверить, есть ли выбранные пользователи через UI Telegram
    # В Telegram Bot API данные приходят в поле users_shared как объект UsersShared
    users_shared = getattr(message, 'users_shared', None)
    
    if users_shared:
        logger.info(f"Обнаружен users_shared: {users_shared}, type: {type(users_shared)}")
        logger.info(f"users_shared атрибуты: {dir(users_shared)}")
        
        # UsersShared содержит поле user_ids - список ID выбранных пользователей
        if hasattr(users_shared, 'user_ids') and users_shared.user_ids and len(users_shared.user_ids) > 0:
            target_telegram_id = users_shared.user_ids[0]
        elif hasattr(users_shared, 'user_id'):
            target_telegram_id = users_shared.user_id
        else:
            logger.error(f"Не удалось извлечь user_id из users_shared: {users_shared}")
            await message.answer("❌ Ошибка: не удалось определить ID выбранного пользователя.")
            return
        
        logger.info(f"Выбран пользователь через UI: {target_telegram_id}")
        
        state_data = await state.get_data()
        action = state_data.get("admin_action")
        
        if not action:
            await message.answer("❌ Ошибка: действие не определено.")
            await state.clear()
            return
        
        try:
            # Для users_shared может не быть username, поэтому используем только ID
            # Username будет обновлен при следующем взаимодействии пользователя с ботом
            username_display = f"ID {target_telegram_id}"
            
            if action == "allow":
                await db.allow_user(target_telegram_id)
                await db.ensure_user(target_telegram_id, None)  # Username обновится автоматически
                result_text = f"✅ Пользователю {target_telegram_id} разрешен доступ."
                logger.info(f"Администратор {user_id} разрешил доступ пользователю {target_telegram_id}")
            elif action == "set_admin":
                await db.set_user_admin(target_telegram_id, is_admin=True)
                await db.ensure_user(target_telegram_id, None)  # Username обновится автоматически
                result_text = f"👑 Пользователю {target_telegram_id} назначены права администратора."
                logger.info(f"Администратор {user_id} назначил администратором пользователя {target_telegram_id}")
            else:
                await message.answer("❌ Неизвестное действие.")
                await state.clear()
                return
            
            await state.clear()
            # Убрать reply-клавиатуру
            await message.answer(
                result_text,
                reply_markup=get_main_keyboard()
            )
            await message.answer(
                "⚙️ <b>Админка</b>",
                reply_markup=get_admin_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при выполнении административного действия: {e}", exc_info=True)
            await message.answer(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
    
    # Если это не выбор пользователя через UI, проверяем другие варианты
    if message.contact:
        # Обработка контакта
        contact: Contact = message.contact
        target_telegram_id = contact.user_id
        
        state_data = await state.get_data()
        action = state_data.get("admin_action")
        
        if not action:
            await message.answer("❌ Ошибка: действие не определено.")
            await state.clear()
            return
        
        try:
            if action == "allow":
                await db.allow_user(target_telegram_id)
                await db.ensure_user(target_telegram_id, contact.first_name)
                result_text = f"✅ Пользователю {target_telegram_id} ({contact.first_name}) разрешен доступ."
                logger.info(f"Администратор {user_id} разрешил доступ пользователю {target_telegram_id}")
            elif action == "set_admin":
                await db.set_user_admin(target_telegram_id, is_admin=True)
                await db.ensure_user(target_telegram_id, contact.first_name)
                result_text = f"👑 Пользователю {target_telegram_id} ({contact.first_name}) назначены права администратора."
                logger.info(f"Администратор {user_id} назначил администратором пользователя {target_telegram_id}")
            else:
                await message.answer("❌ Неизвестное действие.")
                await state.clear()
                return
            
            await state.clear()
            await message.answer(
                result_text,
                reply_markup=get_main_keyboard()
            )
            await message.answer(
                "⚙️ <b>Админка</b>",
                reply_markup=get_admin_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
            return
        except Exception as e:
            logger.error(f"Ошибка при выполнении административного действия: {e}", exc_info=True)
            await message.answer(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_main_keyboard()
            )
            await state.clear()
            return
    
    # Если это текстовое сообщение (Telegram ID)
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте контакт или Telegram ID пользователя.\n\n"
            "Используйте кнопку '👤 Выбрать пользователя' или отправьте число (Telegram ID).",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Проверка на отмену
    if message.text.strip().lower() in ["отмена", "cancel", "❌ отмена"]:
        await state.clear()
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_menu_keyboard())
        return
    
    try:
        target_telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Неверный формат Telegram ID. Используйте число.\n\n"
            "Или используйте кнопку '👤 Выбрать пользователя' для выбора через UI Telegram.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    state_data = await state.get_data()
    action = state_data.get("admin_action")
    
    if not action:
        await message.answer("❌ Ошибка: действие не определено.")
        await state.clear()
        return
    
    try:
        if action == "allow":
            await db.allow_user(target_telegram_id)
            await db.ensure_user(target_telegram_id)
            result_text = f"✅ Пользователю {target_telegram_id} разрешен доступ."
            logger.info(f"Администратор {user_id} разрешил доступ пользователю {target_telegram_id}")
        elif action == "set_admin":
            await db.set_user_admin(target_telegram_id, is_admin=True)
            await db.ensure_user(target_telegram_id)
            result_text = f"👑 Пользователю {target_telegram_id} назначены права администратора."
            logger.info(f"Администратор {user_id} назначил администратором пользователя {target_telegram_id}")
        else:
            await message.answer("❌ Неизвестное действие.")
            await state.clear()
            return
        
        await state.clear()
        await message.answer(
            result_text,
            reply_markup=get_main_keyboard()
        )
        await message.answer(
            "⚙️ <b>Админка</b>",
            reply_markup=get_admin_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка при выполнении административного действия: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
    
    # Берем первого выбранного пользователя
    selected_user = message.users_requested[0]
    target_telegram_id = selected_user.id
    
    state_data = await state.get_data()
    action = state_data.get("admin_action")
    
    if not action:
        await message.answer("❌ Ошибка: действие не определено.")
        await state.clear()
        return
    
    try:
        username = selected_user.username or selected_user.first_name or "без username"
        
        if action == "allow":
            await db.allow_user(target_telegram_id)
            await db.ensure_user(target_telegram_id, selected_user.username)
            result_text = f"✅ Пользователю {target_telegram_id} ({username}) разрешен доступ."
            logger.info(f"Администратор {user_id} разрешил доступ пользователю {target_telegram_id}")
        elif action == "set_admin":
            await db.set_user_admin(target_telegram_id, is_admin=True)
            await db.ensure_user(target_telegram_id, selected_user.username)
            result_text = f"👑 Пользователю {target_telegram_id} ({username}) назначены права администратора."
            logger.info(f"Администратор {user_id} назначил администратором пользователя {target_telegram_id}")
        else:
            await message.answer("❌ Неизвестное действие.")
            await state.clear()
            return
        
        await state.clear()
        # Убрать reply-клавиатуру
        await message.answer(
            result_text,
            reply_markup=get_main_keyboard()
        )
        await message.answer(
            "⚙️ <b>Админка</b>",
            reply_markup=get_admin_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка при выполнении административного действия: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()


# Обработка контактов и текстовых сообщений теперь объединена в один обработчик выше


@router.message(lambda m: m.text == "❌ Отмена", AdminStates.waiting_for_user_contact)
@router.message(lambda m: m.text == "❌ Отмена", AdminStates.waiting_for_user_selection)
async def admin_cancel_handler(message: Message, state: FSMContext):
    """Отмена административного действия"""
    from handlers.keyboards import get_admin_menu_keyboard
    
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=get_admin_menu_keyboard())


@router.message(Command("sync"))
async def sync_handler(message: Message):
    """Принудительная синхронизация с NextCloud"""
    from services.sync_service import SyncService
    
    sync_message = await message.answer("🔄 Синхронизация с NextCloud...")
    
    try:
        sync_service = SyncService()
        
        if not sync_service.enabled:
            await sync_message.edit_text("❌ Синхронизация отключена. Проверьте настройки в .env")
            return
        
        # Callback для обновления прогресса с защитой от флуда
        from datetime import datetime, timedelta
        
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
                reply_markup=get_main_keyboard()
            )
        elif sync_to:
            await sync_message.edit_text(
                "✅ Изменения загружены в NextCloud\n⚠️ Не удалось загрузить изменения из NextCloud",
                reply_markup=get_main_keyboard()
            )
        elif sync_from:
            await sync_message.edit_text(
                "✅ Изменения загружены из NextCloud\n⚠️ Не удалось загрузить изменения в NextCloud",
                reply_markup=get_main_keyboard()
            )
        else:
            await sync_message.edit_text(
                "❌ Ошибка при синхронизации. Проверьте логи.",
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        await sync_message.edit_text(
            f"❌ Ошибка при синхронизации: {str(e)}",
            reply_markup=get_main_keyboard()
        )

