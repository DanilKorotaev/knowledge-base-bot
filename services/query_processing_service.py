"""
Сервис для обработки запросов пользователей
"""
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from aiogram.types import Message, InlineKeyboardMarkup

from services.cursor_cli_service import CursorCLIService
from services.sync_service import SyncService
from utils.db_helpers import get_db
from utils.message_helpers import send_formatted_message, format_file_changes_info
from utils.constants import MessageRole, ChangeType
from handlers.keyboards import get_active_session_keyboard

logger = logging.getLogger(__name__)


class QueryProcessingService:
    """Сервис для обработки запросов пользователей через Cursor CLI"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self._db = None
        self._sync_service = None
        self._cursor_service = None
    
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
        
        # Отправить индикатор "печатает..."
        typing_message = await message.answer("⏳ Обрабатываю запрос...")
        
        start_time = time.time()
        
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
            
            # Обработать запрос через Cursor CLI
            response, changes = await cursor_service.process_query(
                query=query,
                session_id=session_id,
                session_messages=session_messages,
                attached_files=attached_files,
                cursor_chat_id=cursor_chat_id
            )
            
            # Если --resume вернул ошибку, пробуем fallback без cursor_chat_id
            if cursor_chat_id and response.startswith("❌") and "код: 1" in response:
                logger.warning(f"--resume не сработал для chatId={cursor_chat_id}, fallback на ручную историю")
                # Обнулить cursor_chat_id в БД
                await db.update_session(session_id, cursor_chat_id="")
                # Повторить запрос без --resume (с ручной передачей истории)
                response, changes = await cursor_service.process_query(
                    query=query,
                    session_id=session_id,
                    session_messages=session_messages,
                    attached_files=attached_files,
                    cursor_chat_id=None
                )
            
            cursor_time = time.time() - cursor_start
            logger.info(f"⏱️ Cursor CLI обработка заняла: {cursor_time:.2f}с")
            
            # Удалить индикатор "печатает..."
            try:
                await typing_message.delete()
            except Exception:
                pass
            
            # Отправить ответ пользователю
            await send_formatted_message(message, response)
            
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
            
            raise
    
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
        
        # Синхронизировать изменения с NextCloud
        sync_success = await sync_service.sync_changes(changes)
        
        # Форматировать информацию об изменениях
        changes_info = format_file_changes_info(changes, sync_success)
        
        # Отправить информацию об изменениях
        try:
            await message.answer(changes_info, reply_markup=get_active_session_keyboard())
        except Exception as e:
            logger.warning(f"Не удалось отправить информацию об изменениях: {e}")

