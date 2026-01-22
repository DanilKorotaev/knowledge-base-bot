"""
Константы для Knowledge Base Bot
"""
from enum import Enum


class SessionType(str, Enum):
    """Типы сессий"""
    QUERY_WITH_KB = "query_with_kb"
    EMPTY_CHAT = "empty_chat"
    
    def __str__(self) -> str:
        return self.value


class SessionStatus(str, Enum):
    """Статусы сессий"""
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"
    
    def __str__(self) -> str:
        return self.value


class MessageRole(str, Enum):
    """Роли сообщений"""
    USER = "user"
    ASSISTANT = "assistant"
    
    def __str__(self) -> str:
        return self.value


class ChangeType(str, Enum):
    """Типы изменений файлов"""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    
    def __str__(self) -> str:
        return self.value

