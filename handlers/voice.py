"""
Обработчики голосовых сообщений
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


async def voice_filter(message: Message) -> bool:
    """Фильтр для голосовых сообщений"""
    return message.voice is not None


@router.message(voice_filter)
async def voice_handler(message: Message, state: FSMContext):
    """Обработчик голосовых сообщений"""
    # TODO: Реализовать обработку голосовых сообщений
    # 1. Скачать голосовой файл из Telegram
    # 2. Отправить в Whisper API для транскрибации
    # 3. Сохранить транскрипцию в БД
    # 4. Обработать транскрипцию как текстовое сообщение
    # 5. Отправить красивую расшифровку пользователю
    
    await message.answer(
        "🎤 Получено голосовое сообщение.\n\n"
        "Обработка голосовых сообщений будет реализована позже."
    )

