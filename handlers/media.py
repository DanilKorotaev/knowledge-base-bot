"""
Обработчики фото и файлов
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


async def photo_filter(message: Message) -> bool:
    """Фильтр для фото"""
    return message.photo is not None


@router.message(photo_filter)
async def photo_handler(message: Message, state: FSMContext):
    """Обработчик фото"""
    # TODO: Реализовать обработку фото
    # 1. Получить фото из Telegram
    # 2. Скачать файл во временную директорию
    # 3. Опционально: использовать Vision API для извлечения текста
    # 4. Сохранить файл в локальную копию базы знаний
    # 5. Привязать к активной сессии
    # 6. Синхронизировать с NextCloud
    # 7. Уведомить пользователя о сохранении
    
    await message.answer(
        "📷 Получено фото.\n\n"
        "Обработка фото будет реализована позже."
    )


async def document_filter(message: Message) -> bool:
    """Фильтр для документов"""
    return message.document is not None


@router.message(document_filter)
async def document_handler(message: Message, state: FSMContext):
    """Обработчик документов"""
    # TODO: Реализовать обработку документов
    # 1. Получить документ из Telegram
    # 2. Скачать файл во временную директорию
    # 3. Определить тип файла
    # 4. Сохранить файл в локальную копию базы знаний
    # 5. Привязать к активной сессии
    # 6. Синхронизировать с NextCloud
    # 7. Уведомить пользователя о сохранении
    
    await message.answer(
        f"📄 Получен документ: {message.document.file_name}\n\n"
        "Обработка документов будет реализована позже."
    )

