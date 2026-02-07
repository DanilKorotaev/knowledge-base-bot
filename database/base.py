"""
Базовый интерфейс для работы с базой данных
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class DatabaseInterface(ABC):
    """Интерфейс для работы с базой данных"""
    
    @abstractmethod
    async def init_db(self) -> None:
        """Инициализация базы данных (создание таблиц)"""
        pass
    
    @abstractmethod
    async def ensure_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Создать или обновить пользователя"""
        pass
    
    @abstractmethod
    async def create_session(
        self,
        user_id: int,
        session_type: str,
        status: str = "active",
        context_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Создать новую сессию"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Получить сессию по ID"""
        pass
    
    @abstractmethod
    async def get_active_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить активную сессию пользователя"""
        pass
    
    @abstractmethod
    async def get_user_sessions(
        self,
        user_id: int,
        limit: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список сессий пользователя"""
        pass
    
    @abstractmethod
    async def update_session(
        self,
        session_id: int,
        status: Optional[str] = None,
        context_files: Optional[List[str]] = None,
        cursor_chat_id: Optional[str] = None
    ) -> None:
        """Обновить сессию"""
        pass
    
    @abstractmethod
    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str
    ) -> Dict[str, Any]:
        """Добавить сообщение в сессию"""
        pass
    
    @abstractmethod
    async def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю сообщений сессии"""
        pass
    
    @abstractmethod
    async def add_attachment(
        self,
        session_id: int,
        message_id: Optional[int],
        file_type: str,
        file_id: str,
        file_path: Optional[str] = None,
        file_name: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Добавить вложение"""
        pass
    
    @abstractmethod
    async def get_session_attachments(self, session_id: int) -> List[Dict[str, Any]]:
        """Получить вложения сессии"""
        pass
    
    @abstractmethod
    async def add_transcription(
        self,
        attachment_id: int,
        text: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Добавить транскрипцию"""
        pass
    
    @abstractmethod
    async def get_last_voice_attachment(
        self,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить последнее голосовое сообщение пользователя"""
        pass
    
    @abstractmethod
    async def get_transcription(
        self,
        attachment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить транскрипцию по ID вложения"""
        pass
    
    @abstractmethod
    async def log_file_change(
        self,
        session_id: int,
        file_path: str,
        change_type: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None,
        file_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """Залогировать изменение файла"""
        pass
    
    @abstractmethod
    async def get_file_changes(
        self,
        session_id: Optional[int] = None,
        file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю изменений файлов"""
        pass
    
    @abstractmethod
    async def get_file_change(self, change_id: int) -> Optional[Dict[str, Any]]:
        """Получить конкретное изменение"""
        pass
    
    @abstractmethod
    async def is_user_allowed(self, telegram_id: int) -> bool:
        """Проверить, разрешен ли доступ пользователю"""
        pass
    
    @abstractmethod
    async def is_user_admin(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        pass
    
    @abstractmethod
    async def allow_user(self, telegram_id: int) -> None:
        """Разрешить доступ пользователю"""
        pass
    
    @abstractmethod
    async def disallow_user(self, telegram_id: int) -> None:
        """Запретить доступ пользователю"""
        pass
    
    @abstractmethod
    async def set_user_admin(self, telegram_id: int, is_admin: bool) -> None:
        """Установить права администратора пользователю"""
        pass
    
    @abstractmethod
    async def get_allowed_users(self) -> List[Dict[str, Any]]:
        """Получить список всех разрешенных пользователей"""
        pass

