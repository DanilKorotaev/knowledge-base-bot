"""
Обработчики команд бота
"""
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

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
    help_text = """
📚 **Доступные команды:**

/start - Начать работу с ботом
/help - Показать эту справку
/new_query - Начать новый запрос с контекстом базы знаний
/new_chat - Начать пустой чат (без контекста)
/end_query - Завершить текущий запрос
/cancel - Отменить текущую операцию
/transcribe - Расшифровать последнее голосовое сообщение
/history - Показать историю изменений текущей сессии
/revert [change_id] - Откатить конкретное изменение
/revert_session - Откатить все изменения текущей сессии
/sync - Принудительная синхронизация с NextCloud
    """
    await message.answer(help_text)


@router.message(Command("new_query"))
async def new_query_handler(message: Message, state: FSMContext):
    """Начать новый запрос с контекстом базы знаний"""
    # TODO: Реализовать создание сессии
    await message.answer(
        "✅ Начат новый запрос с контекстом базы знаний.\n"
        "Отправьте ваш вопрос текстом, голосом или с файлами."
    )


@router.message(Command("new_chat"))
async def new_chat_handler(message: Message, state: FSMContext):
    """Начать пустой чат (без контекста базы знаний)"""
    # TODO: Реализовать создание сессии
    await message.answer(
        "✅ Начат новый чат без контекста базы знаний.\n"
        "Отправьте ваш вопрос текстом, голосом или с файлами."
    )


@router.message(Command("end_query"))
async def end_query_handler(message: Message, state: FSMContext):
    """Завершить текущий запрос"""
    # TODO: Реализовать завершение сессии
    await message.answer("✅ Запрос завершен.")


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    """Отменить текущую операцию"""
    await state.clear()
    await message.answer("❌ Операция отменена.")


@router.message(Command("transcribe"))
async def transcribe_handler(message: Message):
    """Расшифровать последнее голосовое сообщение"""
    # TODO: Реализовать транскрибацию
    await message.answer("🎤 Функция транскрибации будет реализована позже.")


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

