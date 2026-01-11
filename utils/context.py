"""
Утилиты для управления контекстом сессий
"""
from typing import Optional, List, Dict, Any
from database import DatabaseInterface


class SessionContext:
    """Управление контекстом сессий"""
    
    def __init__(self, db: DatabaseInterface):
        self.db = db
    
    async def get_session_context(
        self,
        session_id: int
    ) -> Dict[str, Any]:
        """Получить контекст сессии"""
        session = await self.db.get_session(session_id)
        if not session:
            return {}
        
        messages = await self.db.get_session_messages(session_id)
        attachments = await self.db.get_session_attachments(session_id)
        
        return {
            "session": session,
            "messages": messages,
            "attachments": attachments
        }
    
    async def build_query_context(
        self,
        session_id: int,
        user_message: str
    ) -> str:
        """Построить контекст для запроса"""
        context_parts = []
        
        session = await self.db.get_session(session_id)
        if session and session.get("context_files"):
            context_parts.append("Контекстные файлы:")
            for file_path in session["context_files"]:
                context_parts.append(f"- {file_path}")
        
        messages = await self.db.get_session_messages(session_id, limit=10)
        if messages:
            context_parts.append("\nИстория сообщений:")
            for msg in messages:
                role = "Пользователь" if msg["role"] == "user" else "Ассистент"
                context_parts.append(f"{role}: {msg['content'][:100]}...")
        
        context_parts.append(f"\nНовое сообщение пользователя: {user_message}")
        
        return "\n".join(context_parts)

