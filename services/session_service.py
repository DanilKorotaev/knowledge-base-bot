"""
Сервис для управления сессиями
"""
import logging
from typing import Optional, Dict, Any, Tuple
from utils.db_helpers import get_db
from utils.constants import SessionType, SessionStatus

logger = logging.getLogger(__name__)


class SessionService:
    """Сервис для управления сессиями пользователей"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self._db = None
    
    async def _get_db(self):
        """Получить экземпляр БД (lazy loading)"""
        if self._db is None:
            self._db = await get_db()
        return self._db
    
    async def get_or_create_active_session(
        self,
        user_id: int,
        username: Optional[str] = None,
        session_type: SessionType = SessionType.QUERY_WITH_KB
    ) -> Dict[str, Any]:
        """
        Получить активную сессию пользователя или создать новую
        
        Args:
            user_id: Telegram ID пользователя
            username: Имя пользователя (опционально)
            session_type: Тип сессии
        
        Returns:
            Dict: Информация о сессии
        """
        db = await self._get_db()
        
        # Убедиться, что пользователь существует
        user = await db.ensure_user(user_id, username)
        
        # Получить активную сессию
        active_session = await db.get_active_session(user["id"])
        
        if not active_session:
            # Создать новую сессию
            active_session = await db.create_session(
                user_id=user["id"],
                session_type=str(session_type),
                status=str(SessionStatus.ACTIVE)
            )
            logger.info(f"Создана новая сессия #{active_session['id']} для пользователя {user_id}")
        
        return active_session
    
    async def ensure_user_and_session(
        self,
        user_id: int,
        username: Optional[str] = None,
        session_type: SessionType = SessionType.QUERY_WITH_KB
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Убедиться, что пользователь существует и получить/создать активную сессию
        
        Args:
            user_id: Telegram ID пользователя
            username: Имя пользователя (опционально)
            session_type: Тип сессии
        
        Returns:
            Tuple[Dict, Dict]: (пользователь, сессия)
        """
        db = await self._get_db()
        
        # Убедиться, что пользователь существует
        user = await db.ensure_user(user_id, username)
        
        # Получить или создать активную сессию
        session = await self.get_or_create_active_session(user_id, username, session_type)
        
        return user, session
    
    async def deactivate_current_session(self, user_id: int) -> None:
        """
        Деактивировать текущую активную сессию пользователя
        
        Args:
            user_id: Telegram ID пользователя
        """
        db = await self._get_db()
        
        # Преобразовать Telegram ID в внутренний DB ID
        user = await db.ensure_user(user_id)
        
        # Получить активную сессию по внутреннему DB ID
        active_session = await db.get_active_session(user["id"])
        
        if active_session:
            await db.update_session(active_session["id"], status=str(SessionStatus.COMPLETED))
            logger.info(f"Сессия #{active_session['id']} деактивирована для пользователя {user_id}")
    
    async def create_new_session(
        self,
        user_id: int,
        username: Optional[str] = None,
        session_type: SessionType = SessionType.QUERY_WITH_KB
    ) -> Dict[str, Any]:
        """
        Создать новую сессию (деактивировав текущую активную)
        
        Args:
            user_id: Telegram ID пользователя
            username: Имя пользователя (опционально)
            session_type: Тип сессии
        
        Returns:
            Dict: Информация о новой сессии
        """
        # Деактивировать текущую сессию
        await self.deactivate_current_session(user_id)
        
        # Создать новую сессию
        return await self.get_or_create_active_session(user_id, username, session_type)
    
    async def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить сессию по ID
        
        Args:
            session_id: ID сессии
        
        Returns:
            Dict: Информация о сессии или None если не найдена
        """
        db = await self._get_db()
        return await db.get_session(session_id)
    
    async def update_session(
        self,
        session_id: int,
        status: Optional[SessionStatus] = None,
        context_files: Optional[list] = None,
        cursor_chat_id: Optional[str] = None,
        display_title: Optional[str] = None,
    ) -> None:
        """
        Обновить сессию
        
        Args:
            session_id: ID сессии
            status: Новый статус (опционально)
            context_files: Новые файлы контекста (опционально)
            cursor_chat_id: ID чата Cursor CLI (опционально)
            display_title: Заголовок для клиентов API (опционально)
        """
        db = await self._get_db()
        
        status_str = str(status) if status else None
        await db.update_session(
            session_id,
            status=status_str,
            context_files=context_files,
            cursor_chat_id=cursor_chat_id,
            display_title=display_title,
        )

