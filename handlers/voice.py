"""
Обработчики голосовых сообщений
"""
import logging
import uuid
from pathlib import Path

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from handlers.keyboards import (
    get_confirm_query_keyboard, get_transcribe_inline_keyboard, get_collecting_messages_keyboard,
    get_voice_action_collecting_keyboard, get_voice_action_normal_keyboard,
    get_voice_collected_keyboard
)
from handlers.states import QueryStates
from services.openai_service import OpenAIService
from services.query_processing_service import QueryProcessingService
from services.session_service import SessionService
from services.transcription_service import TranscriptionService
from utils.constants import SessionType, MessageRole
from utils.db_helpers import get_db
from utils.error_helpers import send_error_message, handle_error_silently
from utils.file_helpers import download_telegram_file
from utils.message_helpers import markdown_to_html
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state

router = Router()
logger = logging.getLogger(__name__)


async def voice_filter(message: Message) -> bool:
    """Фильтр для голосовых сообщений"""
    return message.voice is not None


@router.message(voice_filter)
async def voice_handler(message: Message, state: FSMContext):
    """Обработчик голосовых сообщений - всегда расшифровывает и спрашивает действие"""
    user_id = message.from_user.id
    voice = message.voice
    
    logger.info(f"Получено голосовое сообщение от пользователя {user_id}, длительность: {voice.duration}с")
    
    # Отправить уведомление о начале обработки
    processing_message = await message.answer("🎤 Обрабатываю голосовое сообщение...")
    
    try:
        # Обновить сообщение о процессе
        await processing_message.edit_text("📥 Скачиваю голосовое сообщение...")
        
        # Скачать голосовой файл
        audio_path = await download_telegram_file(message.bot, voice.file_id)
        if not audio_path:
            await processing_message.edit_text("❌ Не удалось скачать голосовое сообщение.")
            return
        
        logger.info(f"Голосовой файл скачан: {audio_path}")
        
        # Обновить сообщение о процессе
        await processing_message.edit_text("🎙️ Расшифровываю голосовое сообщение...")
        
        # Транскрибировать голосовое сообщение
        openai_service = OpenAIService()
        transcription_service = TranscriptionService(openai_service)
        
        transcription_result = await transcription_service.transcribe(str(audio_path))
        transcribed_text = transcription_result.get("text", "")
        language = transcription_result.get("language", "unknown")
        
        if not transcribed_text:
            await processing_message.edit_text("❌ Не удалось расшифровать голосовое сообщение.")
            return
        
        logger.info(f"Транскрибация завершена, язык: {language}, длина текста: {len(transcribed_text)}")
        
        # === Проверить режим сбора сообщений ===
        current_state = await state.get_state()
        if current_state == QueryStates.collecting_messages.state:
            # Режим сбора: автоматически прикрепить голосовое к запросу
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if (
                state_data.get("text_parts") or state_data.get("voice_files") or state_data.get("media_files")
            ) else QueryBuilder()
            builder.add_voice(voice.file_id, audio_path, transcribed_text)
            
            # Сохранить builder + ссылку на транскрипцию для кнопок
            voice_id = str(uuid.uuid4())
            new_state = query_builder_to_state(builder)
            new_state[f"voice_ref_{voice_id}"] = {
                "transcription": transcribed_text,
                "file_id": voice.file_id
            }
            await state.update_data(**new_state)
            
            logger.info(f"Голосовое автоматически добавлено в режим сбора. Всего голосовых: {len(builder.voice_files)}")
            
            # Показать информационное сообщение со сводкой и кнопкой исправления
            summary = builder.get_summary()
            
            await processing_message.edit_text(
                f"✅ Голосовое сообщение добавлено.\n\n"
                f"{summary}\n\n"
                f"Продолжайте добавлять сообщения или нажмите '✅ Завершить сбор'.",
                reply_markup=get_voice_collected_keyboard(voice_id),
                parse_mode=None
            )
            
            # Отправить чистую расшифровку отдельным сообщением для проверки и удобного копирования
            try:
                html_text = markdown_to_html(transcribed_text)
                await message.answer(html_text, parse_mode=ParseMode.HTML)
            except Exception:
                await message.answer(transcribed_text)
            
            # Показать кнопку подтверждения отправки
            await message.answer(
                "Готовы отправить запрос?",
                reply_markup=get_confirm_query_keyboard()
            )
            return
        
        # === Обычный режим ===
        # Создать уникальный ID для этого голосового сообщения
        voice_id = str(uuid.uuid4())
        
        # Сохранить транскрипцию во временное хранилище до выбора пользователя
        await state.update_data(**{
            f"voice_{voice_id}": {
                "file_id": voice.file_id,
                "audio_path": str(audio_path),
                "transcribed_text": transcribed_text,
                "language": language,
                "file_size": voice.file_size,
                "message_id": message.message_id
            }
        })
        
        # Удалить сообщение о процессе
        try:
            await processing_message.delete()
        except Exception:
            pass
        
        # Отправить информационное сообщение о расшифровке
        info_text = "🎤 Расшифровка готова"
        if language and language != "unknown":
            info_text += f" (🌐 {language})"
        await message.answer(info_text)
        
        # Отправить чистую расшифровку отдельным сообщением для удобного копирования/пересылки
        try:
            html_text = markdown_to_html(transcribed_text)
            await message.answer(html_text, parse_mode=ParseMode.HTML)
        except Exception:
            await message.answer(transcribed_text)
        
        # Обычный режим - показать выбор: отправить запрос, использовать как prompt или только транскрибировать
        await message.answer(
            "❓ Что сделать с этим голосовым сообщением?",
            reply_markup=get_voice_action_normal_keyboard(voice_id)
        )
        
    except Exception as e:
        await send_error_message(
            event=processing_message if 'processing_message' in locals() else message,
            error=e,
            user_message=f"❌ Произошла ошибка при обработке голосового сообщения: {str(e)}",
            log_message=f"Ошибка при обработке голосового сообщения от пользователя {user_id}"
        )

