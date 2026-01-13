"""
Обработчики голосовых сообщений
"""
import logging
import time
from pathlib import Path
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from services.transcription_service import TranscriptionService
from services.openai_service import OpenAIService
from services.cursor_cli_service import CursorCLIService
from services.sync_service import SyncService
from utils.file_helpers import download_telegram_file
from utils.message_helpers import split_long_message, markdown_to_html, escape_markdown_v2
from utils.db_helpers import get_db

router = Router()
logger = logging.getLogger(__name__)


async def voice_filter(message: Message) -> bool:
    """Фильтр для голосовых сообщений"""
    return message.voice is not None


async def process_text_query_after_transcription(
    query: str,
    message: Message,
    state: FSMContext,
    session_id: int
):
    """
    Обработать транскрибированный текст как обычный запрос
    Переиспользует логику из messages.py
    """
    from utils.db_helpers import get_db
    
    db = await get_db()
    
    # Сохранить сообщение пользователя в сессию
    await db.add_message(session_id, "user", query)
    
    # Получить историю сообщений сессии для контекста
    session_messages = await db.get_session_messages(session_id)
    logger.debug(f"Загружена история сессии: {len(session_messages)} сообщений")
    
    # Отправить индикатор "печатает..."
    typing_message = await message.answer("⏳ Обрабатываю запрос...")
    
    start_time = time.time()
    
    try:
        # Проверить актуальность базы знаний (быстрая синхронизация из NextCloud)
        sync_service = SyncService()
        sync_updated = False
        
        sync_start = time.time()
        if sync_service.enabled:
            try:
                async def notify_sync(msg: str, is_important: bool = False):
                    """Callback для уведомлений о синхронизации"""
                    if is_important or "Синхронизирую" in msg:
                        try:
                            await typing_message.edit_text(f"⏳ {msg}")
                        except Exception:
                            pass
                
                sync_service.set_notify_callback(notify_sync)
                
                from config import config
                if config.AUTO_SYNC:
                    sync_updated = await sync_service.sync_from_nextcloud(show_notification=True)
            except Exception as e:
                logger.warning(f"Ошибка при проверке синхронизации: {e}")
        
        sync_time = time.time() - sync_start
        if sync_time > 1.0:
            logger.info(f"⏱️ Синхронизация заняла: {sync_time:.2f}с")
        
        # Инициализировать сервис Cursor CLI
        cursor_start = time.time()
        cursor_service = CursorCLIService()
        
        # Обработать запрос через Cursor CLI с контекстом сессии
        response, changes = await cursor_service.process_query(
            query=query,
            session_id=session_id,
            session_messages=session_messages
        )
        
        cursor_time = time.time() - cursor_start
        logger.info(f"⏱️ Cursor CLI обработка заняла: {cursor_time:.2f}с")
        
        # Удалить индикатор "печатает..."
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        # Отправить ответ пользователю
        response_parts = split_long_message(response, max_length=4000)
        
        for i, part in enumerate(response_parts):
            try:
                html_part = markdown_to_html(part)
                await message.answer(html_part, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning(f"Ошибка форматирования HTML: {e}, пробую Markdown V2")
                try:
                    md_part = escape_markdown_v2(part)
                    await message.answer(md_part, parse_mode=ParseMode.MARKDOWN_V2)
                except Exception as e2:
                    logger.warning(f"Ошибка форматирования Markdown V2: {e2}, отправляю без форматирования")
                    await message.answer(part)
        
        # Сохранить ответ ассистента в сессию
        await db.add_message(session_id, "assistant", response)
        
        # Если были изменения файлов, залогировать их и синхронизировать с NextCloud
        if changes:
            for change in changes:
                await db.log_file_change(
                    session_id=session_id,
                    file_path=change.get("path", ""),
                    change_type=change.get("type", "modified"),
                    old_content=change.get("old_content"),
                    new_content=change.get("new_content")
                )
            
            sync_success = await sync_service.sync_changes(changes)
            
            changes_info = f"\n\n📝 Изменено файлов: {len(changes)}"
            if len(changes) <= 5:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes])
                changes_info += f"\n{changes_list}"
            else:
                changes_list = "\n".join([f"  • {ch['path']}" for ch in changes[:5]])
                changes_info += f"\n{changes_list}\n  ... и еще {len(changes) - 5}"
            
            if sync_success:
                changes_info += "\n✅ Изменения синхронизированы с NextCloud"
            else:
                changes_info += "\n⚠️ Не удалось синхронизировать с NextCloud"
            
            try:
                await message.answer(changes_info)
            except Exception as e:
                logger.warning(f"Не удалось отправить информацию об изменениях: {e}")
        
        total_time = time.time() - start_time
        logger.info(f"✅ Запрос обработан успешно за {total_time:.2f}с")
        
    except Exception as e:
        try:
            await typing_message.delete()
        except Exception:
            pass
        
        error_msg = f"❌ Произошла ошибка при обработке запроса: {str(e)}"
        logger.error(f"Ошибка при обработке запроса: {e}", exc_info=True)
        
        try:
            await message.answer(error_msg)
        except Exception:
            pass


@router.message(voice_filter)
async def voice_handler(message: Message, state: FSMContext):
    """Обработчик голосовых сообщений"""
    user_id = message.from_user.id
    voice = message.voice
    
    logger.info(f"Получено голосовое сообщение от пользователя {user_id}, длительность: {voice.duration}с")
    
    # Отправить уведомление о начале обработки
    processing_message = await message.answer("🎤 Обрабатываю голосовое сообщение...")
    
    try:
        # Получить или создать сессию
        db = await get_db()
        user = await db.ensure_user(user_id, message.from_user.username)
        active_session = await db.get_active_session(user["id"])
        
        # Если нет активной сессии, создать новую с контекстом БЗ по умолчанию
        if not active_session:
            active_session = await db.create_session(
                user_id=user["id"],
                session_type="query_with_kb",
                status="active"
            )
            logger.info(f"Создана новая сессия #{active_session['id']} для пользователя {user_id}")
        
        session_id = active_session["id"]
        
        # Обновить сообщение о процессе
        await processing_message.edit_text("📥 Скачиваю голосовое сообщение...")
        
        # Скачать голосовой файл
        audio_path = await download_telegram_file(message.bot, voice.file_id)
        if not audio_path:
            await processing_message.edit_text("❌ Не удалось скачать голосовое сообщение.")
            return
        
        logger.info(f"Голосовой файл скачан: {audio_path}")
        
        # Сохранить вложение в БД
        message_obj = await db.add_message(session_id, "user", "[Голосовое сообщение]")
        attachment = await db.add_attachment(
            session_id=session_id,
            message_id=message_obj["id"],
            file_type="voice",
            file_id=voice.file_id,
            file_path=str(audio_path),
            file_name=f"{voice.file_id}.ogg",
            file_size=voice.file_size
        )
        
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
        
        # Обработать транскрибированный текст как обычный запрос
        await process_text_query_after_transcription(
            transcribed_text,
            message,
            state,
            session_id
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

