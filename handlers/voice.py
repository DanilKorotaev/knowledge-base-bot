"""
Обработчики голосовых сообщений
"""
import logging
from pathlib import Path
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from services.transcription_service import TranscriptionService
from services.openai_service import OpenAIService
from services.query_processing_service import QueryProcessingService
from services.session_service import SessionService
from utils.constants import SessionType, MessageRole
from utils.file_helpers import download_telegram_file
from utils.message_helpers import markdown_to_html
from utils.db_helpers import get_db
from utils.query_builder import QueryBuilder, query_builder_from_state, query_builder_to_state
from handlers.states import QueryStates
from handlers.keyboards import get_confirm_query_keyboard, get_transcribe_inline_keyboard, get_collecting_messages_keyboard

router = Router()
logger = logging.getLogger(__name__)


async def voice_filter(message: Message) -> bool:
    """Фильтр для голосовых сообщений"""
    return message.voice is not None


@router.message(voice_filter)
async def voice_handler(message: Message, state: FSMContext):
    """Обработчик голосовых сообщений"""
    user_id = message.from_user.id
    voice = message.voice
    
    logger.info(f"Получено голосовое сообщение от пользователя {user_id}, длительность: {voice.duration}с")
    
    # Проверить режим сбора сообщений
    current_state = await state.get_state()
    if current_state == QueryStates.collecting_messages.state:
        # Режим сбора сообщений - сохранить во временное хранилище
        processing_message = await message.answer("🎤 Обрабатываю голосовое сообщение для сбора...")
        
        try:
            # Скачать голосовой файл
            await processing_message.edit_text("📥 Скачиваю голосовое сообщение...")
            audio_path = await download_telegram_file(message.bot, voice.file_id)
            if not audio_path:
                await processing_message.edit_text("❌ Не удалось скачать голосовое сообщение.")
                return
            
            # Транскрибировать
            await processing_message.edit_text("🎙️ Расшифровываю голосовое сообщение...")
            openai_service = OpenAIService()
            transcription_service = TranscriptionService(openai_service)
            transcription_result = await transcription_service.transcribe(str(audio_path))
            transcribed_text = transcription_result.get("text", "")
            language = transcription_result.get("language", "unknown")
            
            if not transcribed_text:
                await processing_message.edit_text("❌ Не удалось расшифровать голосовое сообщение.")
                return
            
            # Сохранить во временное хранилище
            state_data = await state.get_data()
            builder = query_builder_from_state(state_data) if state_data.get("voice_files") else QueryBuilder()
            
            builder.add_voice(voice.file_id, audio_path, transcribed_text)
            
            # Сохранить обратно в состояние
            await state.update_data(**query_builder_to_state(builder))
            
            # Показать кнопку подтверждения
            summary = builder.get_summary()
            transcription_preview = transcribed_text[:100] + "..." if len(transcribed_text) > 100 else transcribed_text
            
            await processing_message.edit_text(
                f"✅ Голосовое сообщение добавлено.\n\n"
                f"📝 Расшифровка: {transcription_preview}\n\n"
                f"{summary}\n\n"
                f"Продолжайте добавлять сообщения или нажмите '✅ Завершить сбор' для отправки.",
                reply_markup=get_collecting_messages_keyboard(),
                parse_mode=None  # Явно указываем отсутствие форматирования
            )
            # Также показать inline-кнопку для быстрой отправки
            await message.answer(
                "Готовы отправить запрос?",
                reply_markup=get_confirm_query_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке голосового сообщения в режиме сбора: {e}", exc_info=True)
            await processing_message.edit_text(f"❌ Ошибка: {str(e)}")
        return
    
    # Обычный режим - обработать сразу
    # Отправить уведомление о начале обработки
    processing_message = await message.answer("🎤 Обрабатываю голосовое сообщение...")
    
    try:
        # Получить или создать сессию
        session_service = SessionService()
        active_session = await session_service.get_or_create_active_session(
            user_id=user_id,
            username=message.from_user.username,
            session_type=SessionType.QUERY_WITH_KB
        )
        session_id = active_session["id"]
        
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
        
        # Сохранить сообщение пользователя с транскрипцией
        db = await get_db()
        message_obj = await db.add_message(session_id, str(MessageRole.USER), transcribed_text)
        
        # Сохранить вложение в БД
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=message_obj["id"],
            file_type="voice",
            file_id=voice.file_id,
            file_path=str(audio_path),
            file_name=f"{voice.file_id}.ogg",
            file_size=voice.file_size
        )
        
        # Сохранить транскрипцию в БД
        await db.add_transcription(
            attachment_id=attachment["id"],
            text=transcribed_text,
            language=language
        )
        
        # Отправить красивую расшифровку пользователю
        transcription_display = f"🎤 **Расшифровка:**\n\n{transcribed_text}"
        if language and language != "unknown":
            transcription_display += f"\n\n🌐 Язык: {language}"
        
        try:
            # Пробуем отправить с форматированием
            html_text = markdown_to_html(transcribed_text)
            await processing_message.edit_text(
                f"🎤 <b>Расшифровка:</b>\n\n{html_text}",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            # Если не получилось с HTML, отправляем без форматирования
            await processing_message.edit_text(transcription_display)
        
        # Показать inline-кнопку для повторной расшифровки (если нужно)
        # Кнопка будет показана отдельным сообщением
        try:
            await message.answer(
                "💡 Хотите перерасшифровать это голосовое сообщение?",
                reply_markup=get_transcribe_inline_keyboard()
            )
        except Exception:
            pass  # Игнорируем ошибки при отправке дополнительного сообщения
        
        # Обработать транскрибированный текст как обычный запрос
        # Сообщение пользователя уже сохранено выше, поэтому save_user_message=False
        query_service = QueryProcessingService()
        await query_service.process_query(
            query=transcribed_text,
            session_id=session_id,
            message=message,
            save_user_message=False  # Сообщение уже сохранено выше
        )
        
        # Удалить временный файл
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception as e:
            logger.warning(f"Не удалось удалить временный файл {audio_path}: {e}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения от пользователя {user_id}: {e}", exc_info=True)
        try:
            await processing_message.edit_text(
                f"❌ Произошла ошибка при обработке голосового сообщения: {str(e)}"
            )
        except Exception:
            await message.answer(
                f"❌ Произошла ошибка при обработке голосового сообщения: {str(e)}"
            )

