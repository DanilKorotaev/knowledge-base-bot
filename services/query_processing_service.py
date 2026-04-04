"""
Сервис для обработки запросов пользователей
"""
import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from aiogram.types import Message, LinkPreviewOptions
from aiogram.enums import ParseMode

from config import config as app_config
from services.cursor_cli_service import CursorCLIService, CURSOR_QUERY_CANCELLED_MESSAGE
from services.nextcloud_service import NextCloudService
from services.sync_service import SyncService
from utils.db_helpers import get_db
from utils.message_helpers import send_formatted_message, format_file_changes_info, StreamingMessageUpdater
from utils.constants import MessageRole, ChangeType
from handlers.keyboards import get_active_session_keyboard, get_query_cancel_keyboard
from utils.query_cancel_registry import register_cancel_request, unregister_cancel_request

logger = logging.getLogger(__name__)


def _user_facing_query_error(exc: BaseException) -> str:
    """Краткий текст для Telegram без сырого traceback."""
    if isinstance(exc, asyncio.TimeoutError):
        return (
            "❌ Превышено время ожидания. Попробуйте ещё раз или упростите запрос."
        )
    if isinstance(exc, (ConnectionError, OSError)):
        return (
            "❌ Сетевая или системная ошибка. Проверьте соединение и повторите запрос."
        )
    return "❌ Произошла ошибка при обработке запроса. Попробуйте позже."


def _format_query_elapsed(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} с"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m} мин {s} с"
    h, m2 = divmod(m, 60)
    return f"{h} ч {m2} мин"


async def _run_query_status_timer(
    typing_message: Message,
    stop: asyncio.Event,
    interval_sec: int,
    reply_markup,
    stream_phase: Optional[asyncio.Event] = None,
    session_suffix: str = "",
) -> None:
    """
    Обновляет текст статуса с прошедшим временем, пока stop не установлен.
    Если stream_phase установлен (первый непустой чанк стрима) — текст «Получаю ответ...».
    """
    start = time.time()
    try:
        while not stop.is_set():
            await asyncio.sleep(interval_sec)
            if stop.is_set():
                break
            elapsed = int(time.time() - start)
            label = _format_query_elapsed(elapsed)
            streaming = stream_phase is not None and stream_phase.is_set()
            head = "⏳ Получаю ответ..." if streaming else "⏳ Обрабатываю запрос..."
            line = f"{head}{session_suffix} ({label})"
            try:
                await typing_message.edit_text(
                    line,
                    reply_markup=reply_markup,
                )
            except Exception:
                pass
    except asyncio.CancelledError:
        raise


async def _stop_query_progress_timer(
    timer_stop: asyncio.Event,
    timer_task: Optional[asyncio.Task],
) -> None:
    """Остановить фоновый таймер статуса до любых долгих шагов (синк, уведомления)."""
    timer_stop.set()
    if timer_task is not None and not timer_task.done():
        timer_task.cancel()
        try:
            await timer_task
        except asyncio.CancelledError:
            pass


# Параллельные запросы: у пользователя может быть несколько долгих process_query подряд
# (разные сообщения / сессии). Каждый вызов привязан к своему message и своему typing_message;
# в статусе показываем номер сессии, чтобы отличать ответы.


class QueryProcessingService:
    """Сервис для обработки запросов пользователей через Cursor CLI"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self._db = None
        self._sync_service = None
        self._cursor_service = None
        self._nextcloud_service = None
    
    async def _get_db(self):
        """Получить экземпляр БД (lazy loading)"""
        if self._db is None:
            self._db = await get_db()
        return self._db
    
    def _get_sync_service(self) -> SyncService:
        """Получить экземпляр SyncService"""
        if self._sync_service is None:
            self._sync_service = SyncService()
        return self._sync_service
    
    def _get_cursor_service(self) -> CursorCLIService:
        """Получить экземпляр CursorCLIService"""
        if self._cursor_service is None:
            self._cursor_service = CursorCLIService()
        return self._cursor_service
    
    def _get_nextcloud_service(self) -> NextCloudService:
        """Получить экземпляр NextCloudService"""
        if self._nextcloud_service is None:
            self._nextcloud_service = NextCloudService()
        return self._nextcloud_service
    
    async def process_query(
        self,
        query: str,
        session_id: int,
        message: Message,
        attached_files: Optional[List[Path]] = None,
        save_user_message: bool = True
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Обработать запрос через Cursor CLI
        
        Args:
            query: Текст запроса
            session_id: ID сессии
            message: Объект сообщения Telegram для отправки ответов
            attached_files: Список путей к прикрепленным файлам (опционально)
            save_user_message: Сохранять ли сообщение пользователя в БД (по умолчанию True)
        
        Returns:
            tuple[str, List[Dict]]: (ответ, список изменений файлов)
        """
        db = await self._get_db()
        
        # Получить историю сообщений сессии для контекста
        # Если save_user_message=False, сообщение уже сохранено ранее
        session_messages = await db.get_session_messages(session_id)
        logger.debug(f"Загружена история сессии: {len(session_messages)} сообщений")
        
        user_id = message.from_user.id if message.from_user else 0
        request_id, cancel_event = register_cancel_request(user_id)
        progress_keyboard = get_query_cancel_keyboard(request_id)
        timer_stop = asyncio.Event()
        timer_interval = app_config.QUERY_PROGRESS_TIMER_INTERVAL
        timer_task = None
        stream_phase = asyncio.Event() if app_config.STREAMING_ENABLED else None
        session_suffix = f" · #{session_id}"
        typing_message = await message.answer(
            f"⏳ Обрабатываю запрос{session_suffix}... (0 с)",
            reply_markup=progress_keyboard,
        )
        timer_task = asyncio.create_task(
            _run_query_status_timer(
                typing_message,
                timer_stop,
                timer_interval,
                progress_keyboard,
                stream_phase=stream_phase,
                session_suffix=session_suffix,
            )
        )
        
        start_time = time.time()
        updater = None
        
        try:
            # Проверить актуальность базы знаний (быстрая синхронизация из NextCloud)
            sync_service = self._get_sync_service()
            sync_updated = False
            
            sync_start = time.time()
            if sync_service.enabled:
                try:
                    async def notify_sync(msg: str, is_important: bool = False):
                        """Callback для уведомлений о синхронизации"""
                        if is_important or "Синхронизирую" in msg:
                            try:
                                await typing_message.edit_text(
                                    f"⏳ {msg}",
                                    reply_markup=progress_keyboard,
                                )
                            except Exception:
                                pass
                    
                    sync_service.set_notify_callback(notify_sync)
                    
                    if app_config.AUTO_SYNC:
                        sync_updated = await sync_service.sync_from_nextcloud(show_notification=True)
                except Exception as e:
                    logger.warning(f"Ошибка при проверке синхронизации: {e}")
            
            sync_time = time.time() - sync_start
            if sync_time > 1.0:
                logger.info(f"⏱️ Синхронизация заняла: {sync_time:.2f}с")
            
            # Инициализировать сервис Cursor CLI
            cursor_start = time.time()
            cursor_service = self._get_cursor_service()
            
            # Получить cursor_chat_id из сессии
            session_data = await db.get_session(session_id)
            cursor_chat_id = session_data.get("cursor_chat_id") if session_data else None
            
            # Если cursor_chat_id нет (первый запрос в сессии) — создать чат
            if not cursor_chat_id:
                cursor_chat_id = await cursor_service.create_chat()
                if cursor_chat_id:
                    await db.update_session(session_id, cursor_chat_id=cursor_chat_id)
                    logger.info(f"Создан и сохранён cursor_chat_id={cursor_chat_id} для сессии #{session_id}")
                else:
                    logger.warning(f"Не удалось создать чат Cursor CLI для сессии #{session_id}, используем fallback")
            
            # Создать StreamingMessageUpdater (если стриминг включён)
            streaming_enabled = app_config.STREAMING_ENABLED
            updater = None
            on_chunk_cb = None
            
            if streaming_enabled:
                updater = StreamingMessageUpdater(
                    message=message,
                    typing_message=typing_message,
                    update_interval=app_config.STREAMING_UPDATE_INTERVAL,
                    min_buffer_size=app_config.STREAMING_MIN_BUFFER,
                    reply_markup=progress_keyboard,
                )

                async def wrapped_on_chunk(chunk: str) -> None:
                    if stream_phase is not None and not stream_phase.is_set() and chunk.strip():
                        stream_phase.set()
                    await updater.on_chunk(chunk)

                on_chunk_cb = wrapped_on_chunk
            
            # Обработать запрос через Cursor CLI
            response, changes = await cursor_service.process_query(
                query=query,
                session_id=session_id,
                session_messages=session_messages,
                attached_files=attached_files,
                cursor_chat_id=cursor_chat_id,
                on_chunk=on_chunk_cb,
                cancel_event=cancel_event,
            )
            
            # Если --resume вернул ошибку, пробуем fallback без cursor_chat_id
            if cursor_chat_id and response.startswith("❌") and "код: 1" in response:
                logger.warning(f"--resume не сработал для chatId={cursor_chat_id}, fallback на ручную историю")
                # Обнулить cursor_chat_id в БД
                await db.update_session(session_id, cursor_chat_id="")
                
                # Сбросить updater для повторного запроса
                if streaming_enabled:
                    updater = StreamingMessageUpdater(
                        message=message,
                        typing_message=typing_message,
                        update_interval=app_config.STREAMING_UPDATE_INTERVAL,
                        min_buffer_size=app_config.STREAMING_MIN_BUFFER,
                        reply_markup=progress_keyboard,
                    )

                    async def wrapped_on_chunk_fb(chunk: str) -> None:
                        if stream_phase is not None and not stream_phase.is_set() and chunk.strip():
                            stream_phase.set()
                        await updater.on_chunk(chunk)

                    on_chunk_cb = wrapped_on_chunk_fb
                
                # Повторить запрос без --resume (с ручной передачей истории)
                response, changes = await cursor_service.process_query(
                    query=query,
                    session_id=session_id,
                    session_messages=session_messages,
                    attached_files=attached_files,
                    cursor_chat_id=None,
                    on_chunk=on_chunk_cb,
                    cancel_event=cancel_event,
                )
            
            cursor_time = time.time() - cursor_start
            logger.info(f"⏱️ Cursor CLI обработка заняла: {cursor_time:.2f}с")
            
            if response.strip() == CURSOR_QUERY_CANCELLED_MESSAGE.strip():
                try:
                    await typing_message.edit_text(CURSOR_QUERY_CANCELLED_MESSAGE, reply_markup=None)
                except Exception:
                    try:
                        await typing_message.delete()
                    except Exception:
                        pass
                    await message.answer(CURSOR_QUERY_CANCELLED_MESSAGE)
            elif updater and updater.full_text.strip():
                await updater.finalize()
            else:
                try:
                    await typing_message.delete()
                except Exception:
                    pass
                await send_formatted_message(message, response)

            # До синка и уведомлений об файлах — иначе таймер перезапишет финальный ответ
            await _stop_query_progress_timer(timer_stop, timer_task)
            
            # Сохранить сообщение пользователя в сессию (ПОСЛЕ обработки, чтобы избежать дублирования в контексте)
            if save_user_message:
                await db.add_message(session_id, str(MessageRole.USER), query)
            
            # Сохранить ответ ассистента в сессию
            await db.add_message(session_id, str(MessageRole.ASSISTANT), response)
            
            # Обработать изменения файлов
            await self.handle_file_changes(session_id, changes, message)
            
            total_time = time.time() - start_time
            logger.info(f"✅ Запрос обработан успешно за {total_time:.2f}с")
            
            return response, changes
            
        except Exception as e:
            # При ошибке: финализировать стриминг или удалить typing_message
            try:
                if updater and updater.full_text.strip():
                    await updater.finalize()
                else:
                    await typing_message.delete()
            except Exception:
                pass
            await _stop_query_progress_timer(timer_stop, timer_task)
            
            logger.error(f"Ошибка при обработке запроса: {e}", exc_info=True)
            error_msg = _user_facing_query_error(e)
            try:
                await message.answer(error_msg)
            except Exception:
                pass
            
            raise
        finally:
            # На случай если таймер ещё не остановили (ранний выход / исключение до успешного пути)
            await _stop_query_progress_timer(timer_stop, timer_task)
            unregister_cancel_request(request_id)
    
    async def handle_file_changes(
        self,
        session_id: int,
        changes: List[Dict[str, Any]],
        message: Message
    ) -> None:
        """
        Обработать изменения файлов: залогировать, синхронизировать и уведомить пользователя
        
        Args:
            session_id: ID сессии
            changes: Список изменений файлов
            message: Объект сообщения Telegram для отправки уведомлений
        """
        if not changes:
            # Если изменений не было, показать клавиатуру активной сессии отдельным сообщением
            try:
                await message.answer(
                    "💡 Используйте кнопки ниже для управления сессией.",
                    reply_markup=get_active_session_keyboard()
                )
            except Exception:
                pass  # Игнорируем ошибки
            return
        
        db = await self._get_db()
        sync_service = self._get_sync_service()
        
        # Залогировать изменения в БД
        for change in changes:
            await db.log_file_change(
                session_id=session_id,
                file_path=change.get("path", ""),
                change_type=change.get("type", str(ChangeType.MODIFIED)),
                old_content=change.get("old_content"),
                new_content=change.get("new_content")
            )

        # Path 2 (HealthSync): связать заметку тренировки с JSON, если файлы уже в KB
        try:
            from utils.health_linking_hook import maybe_link_health_for_kb_changes

            maybe_link_health_for_kb_changes(app_config.LOCAL_KB_PATH, changes)
        except Exception as e:
            logger.warning("Health link Path 2 (handle_file_changes): %s", e, exc_info=True)
        
        # Синхронизировать изменения с NextCloud
        sync_success = await sync_service.sync_changes(changes)
        
        # Получить ссылки на файлы в NextCloud (если включено)
        file_urls: Optional[Dict[str, str]] = None
        link_mode = getattr(app_config, 'NEXTCLOUD_LINK_MODE', 'disabled')
        
        if link_mode != "disabled" and sync_success:
            nc_service = self._get_nextcloud_service()
            if nc_service.enabled:
                file_urls = {}
                
                async def get_link_for_change(change: Dict[str, Any]) -> tuple[str, Optional[str]]:
                    path = change.get("path", "")
                    try:
                        url = await nc_service.get_file_link(path)
                        return path, url
                    except Exception as e:
                        logger.debug(f"Не удалось получить ссылку для {path}: {e}")
                        return path, None
                
                # Получить ссылки параллельно
                results = await asyncio.gather(
                    *[get_link_for_change(ch) for ch in changes],
                    return_exceptions=True
                )
                
                for result in results:
                    if isinstance(result, tuple) and result[1]:
                        file_urls[result[0]] = result[1]
                
                if not file_urls:
                    file_urls = None  # Нет ссылок — не передаём
        
        # Форматировать информацию об изменениях
        changes_info = format_file_changes_info(
            changes, sync_success, file_urls=file_urls, link_mode=link_mode
        )
        
        session_keyboard = get_active_session_keyboard()
        
        # Отправить информацию об изменениях (HTML для ссылок и предотвращения авто-ссылок)
        try:
            await message.answer(
                changes_info,
                parse_mode=ParseMode.HTML,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=session_keyboard
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить информацию об изменениях с HTML: {e}")
            # Fallback: отправить без форматирования
            try:
                plain_text = re.sub(r'<[^>]+>', '', changes_info)
                await message.answer(plain_text, reply_markup=session_keyboard)
            except Exception as e2:
                logger.warning(f"Не удалось отправить информацию об изменениях: {e2}")

