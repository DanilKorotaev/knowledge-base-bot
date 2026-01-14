"""
Обработчики команд бота
"""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from utils.db_helpers import get_db
from handlers.states import QueryStates
from handlers.keyboards import get_confirm_query_keyboard
from utils.query_builder import QueryBuilder, query_builder_to_state

router = Router()
logger = logging.getLogger(__name__)


@router.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Привет! Я бот для работы с базой знаний.\n\n"
        "Используйте /help для списка команд."
    )


@router.message(Command("help"))
async def help_handler(message: Message):
    """Обработчик команды /help"""
    help_text = """📚 <b>Доступные команды:</b>

/start - Начать работу с ботом
/help - Показать эту справку
/new_query - Начать новый запрос с контекстом базы знаний
/new_chat - Начать пустой чат (без контекста)
/collect - Включить режим сбора сообщений (текст, голос, файлы)
/stop_collect - Отключить режим сбора сообщений
/end_query - Завершить текущий запрос
/sessions - Показать список ваших сессий
/switch_session &lt;id&gt; - Переключиться на другую сессию
/cancel - Отменить текущую операцию
/transcribe - Расшифровать последнее голосовое сообщение
/history - Показать историю изменений текущей сессии
/revert [change_id] - Откатить конкретное изменение
/revert_session - Откатить все изменения текущей сессии
/sync - Принудительная синхронизация с NextCloud

<b>Режим сбора сообщений:</b>
Используйте /collect для включения режима, в котором можно отправлять несколько сообщений (текст, голос, файлы) перед отправкой запроса. Все сообщения будут собраны вместе и отправлены одним запросом."""
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)


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
    
    await message.answer(
        f"✅ Начат новый запрос с контекстом базы знаний.\n"
        f"Сессия #{session['id']}\n\n"
        f"Отправьте ваш вопрос текстом, голосом или с файлами.\n\n"
        f"Используйте /collect для включения режима сбора сообщений."
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
    
    await message.answer(
        "📝 Режим сбора сообщений включен.\n\n"
        "Теперь вы можете отправлять несколько сообщений:\n"
        "• Текстовые сообщения\n"
        "• Голосовые сообщения\n"
        "• Файлы и фото\n\n"
        "Все сообщения будут собраны вместе. "
        "Когда будете готовы, нажмите кнопку «Отправить запрос».\n\n"
        "Используйте /stop_collect для отключения режима.",
        reply_markup=get_confirm_query_keyboard()
    )


@router.message(Command("stop_collect"))
async def stop_collect_mode_handler(message: Message, state: FSMContext):
    """Отключить режим сбора сообщений"""
    current_state = await state.get_state()
    
    if current_state != QueryStates.collecting_messages.state:
        await message.answer("ℹ️ Режим сбора сообщений не активен.")
        return
    
    # Очистить состояние
    await state.clear()
    
    await message.answer(
        "❌ Режим сбора сообщений отключен.\n"
        "Все собранные данные удалены."
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
    
    await message.answer(
        f"✅ Начат новый чат без контекста базы знаний.\n"
        f"Сессия #{session['id']}\n\n"
        f"Отправьте ваш вопрос текстом, голосом или с файлами."
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
        await message.answer(f"✅ Сессия #{active_session['id']} завершена.")
    else:
        await message.answer("ℹ️ Нет активной сессии для завершения.")


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Отменить текущую операцию"""
    await state.clear()
    await message.answer("❌ Операция отменена.")


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
    db = await get_db()
    user_id = message.from_user.id
    
    # Получить пользователя
    user = await db.ensure_user(user_id, message.from_user.username)
    
    # Получить все сессии пользователя (последние 10)
    sessions = await db.get_user_sessions(user["id"], limit=10)
    
    if not sessions:
        response = "ℹ️ У вас нет сессий.\n\n"
        response += "Используйте /new_query или /new_chat для создания новой сессии."
        await message.answer(response, parse_mode=ParseMode.HTML)
        return
    
    # Найти активную сессию
    active_session = await db.get_active_session(user["id"])
    active_session_id = active_session["id"] if active_session else None
    
    response = "📋 <b>Ваши сессии:</b>\n\n"
    
    for session in sessions:
        session_type_label = "С контекстом БЗ" if session["session_type"] == "query_with_kb" else "Без контекста"
        status_label = "🟢 Активна" if session["id"] == active_session_id else f"⚪ {session['status']}"
        
        messages_count = len(await db.get_session_messages(session["id"]))
        
        response += f"<b>#{session['id']}</b> - {status_label}\n"
        response += f"  Тип: {session_type_label}\n"
        response += f"  Сообщений: {messages_count}\n"
        response += f"  Создана: {session['created_at']}\n\n"
    
    response += "Используйте /switch_session &lt;id&gt; для переключения на другую сессию."
    
    await message.answer(response, parse_mode=ParseMode.HTML)


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
        f"Сообщений: {messages_count}"
    )


@router.message(Command("history"))
async def history_handler(message: Message):
    """Показать историю изменений текущей сессии"""
    # TODO: Реализовать показ истории
    await message.answer("📜 История изменений будет показана позже.")


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
        
        # Синхронизировать в обе стороны
        sync_to = await sync_service.sync_to_nextcloud()
        sync_from = await sync_service.sync_from_nextcloud()
        
        if sync_to and sync_from:
            await sync_message.edit_text("✅ Синхронизация завершена успешно")
        elif sync_to:
            await sync_message.edit_text("✅ Изменения загружены в NextCloud\n⚠️ Не удалось загрузить изменения из NextCloud")
        elif sync_from:
            await sync_message.edit_text("✅ Изменения загружены из NextCloud\n⚠️ Не удалось загрузить изменения в NextCloud")
        else:
            await sync_message.edit_text("❌ Ошибка при синхронизации. Проверьте логи.")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации: {e}", exc_info=True)
        await sync_message.edit_text(f"❌ Ошибка при синхронизации: {str(e)}")

