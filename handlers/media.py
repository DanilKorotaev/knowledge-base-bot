"""
Обработчики фото и файлов
"""
import logging
import shutil
from pathlib import Path
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

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
        logger.info(f"Получено фото в режиме сбора от пользователя {user_id}, file_id: {photo.file_id}")
        processing_message = await message.answer("📷 Обрабатываю фото для сбора...")
        
        try:
            # Скачать фото
            await processing_message.edit_text("📥 Скачиваю фото...")
            logger.debug(f"Начинаю скачивание фото {photo.file_id} из Telegram")
            photo_path = await download_telegram_file(message.bot, photo.file_id)
            if not photo_path:
                logger.error(f"Не удалось скачать фото {photo.file_id}")
                await processing_message.edit_text("❌ Не удалось скачать фото.")
                return
            
            # Логировать информацию о скачанном файле
            if photo_path.exists():
                file_size = photo_path.stat().st_size
                logger.info(f"Фото скачано: {photo_path.name} ({file_size} байт), временный путь: {photo_path}")
            else:
                logger.warning(f"Скачанный файл не найден: {photo_path}")
            
            # Сохранить в локальную копию базы знаний
            kb_path = config.LOCAL_KB_PATH
            attachments_dir = kb_path / "attachments" / "photos"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Директория для фото: {attachments_dir}")
            
            # Переместить файл в папку attachments
            final_path = attachments_dir / f"{photo.file_id}.jpg"
            if photo_path.exists():
                # Используем shutil.move() вместо rename() для работы между разными файловыми системами
                logger.debug(f"Перемещаю фото из {photo_path} в {final_path}")
                shutil.move(str(photo_path), str(final_path))
                photo_path = final_path
                if final_path.exists():
                    file_size = final_path.stat().st_size
                    logger.info(f"Фото сохранено в базе знаний: {final_path.relative_to(kb_path)} ({file_size} байт)")
                else:
                    logger.error(f"Фото не найдено после перемещения: {final_path}")
            else:
                logger.warning(f"Не удалось переместить фото: исходный файл не найден {photo_path}")
            
            # Сохранить во временное хранилище
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if state_data.get("media_files") else QueryBuilder()
            
            builder.add_media(photo.file_id, photo_path, f"{photo.file_id}.jpg", "photo")
            logger.debug(f"Фото добавлено в QueryBuilder: file_id={photo.file_id}, path={photo_path}")
            
            # Сохранить обратно в состояние
            await state.update_data(**query_builder_to_state(builder))
            logger.info(f"Фото успешно добавлено в режим сбора. Всего медиа-файлов: {len(builder.media_files)}")
            
            # Показать кнопку подтверждения
            summary = builder.get_summary()
            await processing_message.edit_text(
                f"✅ Фото добавлено.\n\n{summary}\n\n"
                f"Продолжайте добавлять сообщения или подтвердите отправку.",
                reply_markup=get_confirm_query_keyboard(),
                parse_mode=None  # Явно указываем отсутствие форматирования
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
        file_name = document.file_name or "документ"
        logger.info(f"Получен документ в режиме сбора от пользователя {user_id}, file_id: {document.file_id}, имя: {file_name}")
        processing_message = await message.answer("📄 Обрабатываю документ для сбора...")
        
        try:
            # Скачать документ
            await processing_message.edit_text("📥 Скачиваю документ...")
            logger.debug(f"Начинаю скачивание документа {document.file_id} ({file_name}) из Telegram")
            doc_path = await download_telegram_file(message.bot, document.file_id)
            if not doc_path:
                logger.error(f"Не удалось скачать документ {document.file_id}")
                await processing_message.edit_text("❌ Не удалось скачать документ.")
                return
            
            # Логировать информацию о скачанном файле
            if doc_path.exists():
                file_size = doc_path.stat().st_size
                logger.info(f"Документ скачан: {doc_path.name} ({file_size} байт), временный путь: {doc_path}")
            else:
                logger.warning(f"Скачанный файл не найден: {doc_path}")
            
            # Сохранить в локальную копию базы знаний
            kb_path = config.LOCAL_KB_PATH
            attachments_dir = kb_path / "attachments" / "documents"
            attachments_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Директория для документов: {attachments_dir}")
            
            # Переместить файл в папку attachments
            file_extension = Path(document.file_name).suffix if document.file_name else ""
            final_path = attachments_dir / f"{document.file_id}{file_extension}"
            if doc_path.exists():
                # Используем shutil.move() вместо rename() для работы между разными файловыми системами
                logger.debug(f"Перемещаю документ из {doc_path} в {final_path}")
                shutil.move(str(doc_path), str(final_path))
                doc_path = final_path
                if final_path.exists():
                    file_size = final_path.stat().st_size
                    logger.info(f"Документ сохранен в базе знаний: {final_path.relative_to(kb_path)} ({file_size} байт)")
                else:
                    logger.error(f"Документ не найден после перемещения: {final_path}")
            else:
                logger.warning(f"Не удалось переместить документ: исходный файл не найден {doc_path}")
            
            # Сохранить во временное хранилище
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if state_data.get("media_files") else QueryBuilder()
            
            file_name = document.file_name or f"document{file_extension}"
            builder.add_media(document.file_id, doc_path, file_name, "document")
            logger.debug(f"Документ добавлен в QueryBuilder: file_id={document.file_id}, name={file_name}, path={doc_path}")
            
            # Сохранить обратно в состояние
            await state.update_data(**query_builder_to_state(builder))
            logger.info(f"Документ успешно добавлен в режим сбора. Всего медиа-файлов: {len(builder.media_files)}")
            
            # Показать кнопку подтверждения
            summary = builder.get_summary()
            await processing_message.edit_text(
                f"✅ Документ добавлен: {file_name}\n\n{summary}\n\n"
                f"Продолжайте добавлять сообщения или подтвердите отправку.",
                reply_markup=get_confirm_query_keyboard(),
                parse_mode=None  # Явно указываем отсутствие форматирования
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

