"""
Обработчики фото и файлов
"""
import logging
from pathlib import Path
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from utils.file_helpers import download_telegram_file
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state
from handlers.states import QueryStates
from handlers.keyboards import get_confirm_query_keyboard
from config import config

router = Router()
logger = logging.getLogger(__name__)


async def photo_filter(message: Message) -> bool:
    """Фильтр для фото"""
    return message.photo is not None


@router.message(photo_filter)
async def photo_handler(message: Message, state: FSMContext):
    """Обработчик фото"""
    user_id = message.from_user.id
    photo = message.photo[-1] if message.photo else None  # Берем фото наибольшего размера
    
    if not photo:
        await message.answer("❌ Не удалось получить фото.")
        return
    
    # Проверить режим сбора сообщений
    current_state = await state.get_state()
    if current_state == QueryStates.collecting_messages.state:
        # Режим сбора сообщений - сохранить во временное хранилище
        processing_message = await message.answer("📷 Обрабатываю фото для сбора...")
        
        try:
            # Скачать фото
            await processing_message.edit_text("📥 Скачиваю фото...")
            photo_path = await download_telegram_file(message.bot, photo.file_id)
            if not photo_path:
                await processing_message.edit_text("❌ Не удалось скачать фото.")
                return
            
            # Сохранить в локальную копию базы знаний
            kb_path = config.LOCAL_KB_PATH
            attachments_dir = kb_path / "attachments" / "photos"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            
            # Переместить файл в папку attachments
            final_path = attachments_dir / f"{photo.file_id}.jpg"
            if photo_path.exists():
                photo_path.rename(final_path)
                photo_path = final_path
            
            # Сохранить во временное хранилище
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if state_data.get("media_files") else QueryBuilder()
            
            builder.add_media(photo.file_id, photo_path, f"{photo.file_id}.jpg", "photo")
            
            # Сохранить обратно в состояние
            await state.update_data(**query_builder_to_state(builder))
            
            # Показать кнопку подтверждения
            summary = builder.get_summary()
            await processing_message.edit_text(
                f"✅ Фото добавлено.\n\n{summary}\n\n"
                f"Продолжайте добавлять сообщения или подтвердите отправку.",
                reply_markup=get_confirm_query_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке фото в режиме сбора: {e}", exc_info=True)
            await processing_message.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # Обычный режим - пока заглушка
    await message.answer(
        "📷 Получено фото.\n\n"
        "Обработка фото будет реализована позже.\n"
        "Используйте /collect для включения режима сбора сообщений."
    )


async def document_filter(message: Message) -> bool:
    """Фильтр для документов"""
    return message.document is not None


@router.message(document_filter)
async def document_handler(message: Message, state: FSMContext):
    """Обработчик документов"""
    user_id = message.from_user.id
    document = message.document
    
    if not document:
        await message.answer("❌ Не удалось получить документ.")
        return
    
    # Проверить режим сбора сообщений
    current_state = await state.get_state()
    if current_state == QueryStates.collecting_messages.state:
        # Режим сбора сообщений - сохранить во временное хранилище
        processing_message = await message.answer("📄 Обрабатываю документ для сбора...")
        
        try:
            # Скачать документ
            await processing_message.edit_text("📥 Скачиваю документ...")
            doc_path = await download_telegram_file(message.bot, document.file_id)
            if not doc_path:
                await processing_message.edit_text("❌ Не удалось скачать документ.")
                return
            
            # Сохранить в локальную копию базы знаний
            kb_path = config.LOCAL_KB_PATH
            attachments_dir = kb_path / "attachments" / "documents"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            
            # Переместить файл в папку attachments
            file_extension = Path(document.file_name).suffix if document.file_name else ""
            final_path = attachments_dir / f"{document.file_id}{file_extension}"
            if doc_path.exists():
                doc_path.rename(final_path)
                doc_path = final_path
            
            # Сохранить во временное хранилище
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if state_data.get("media_files") else QueryBuilder()
            
            file_name = document.file_name or f"document{file_extension}"
            builder.add_media(document.file_id, doc_path, file_name, "document")
            
            # Сохранить обратно в состояние
            await state.update_data(**query_builder_to_state(builder))
            
            # Показать кнопку подтверждения
            summary = builder.get_summary()
            await processing_message.edit_text(
                f"✅ Документ добавлен: {file_name}\n\n{summary}\n\n"
                f"Продолжайте добавлять сообщения или подтвердите отправку.",
                reply_markup=get_confirm_query_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке документа в режиме сбора: {e}", exc_info=True)
            await processing_message.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # Обычный режим - пока заглушка
    await message.answer(
        f"📄 Получен документ: {document.file_name}\n\n"
        "Обработка документов будет реализована позже.\n"
        "Используйте /collect для включения режима сбора сообщений."
    )

