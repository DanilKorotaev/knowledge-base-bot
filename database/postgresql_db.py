"""
Реализация работы с PostgreSQL
"""
import asyncpg
from typing import Optional, List, Dict, Any
from .base import DatabaseInterface
from config import config


class PostgreSQLDatabase(DatabaseInterface):
    """Реализация работы с PostgreSQL"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self) -> None:
        """Подключение к базе данных"""
        self.pool = await asyncpg.create_pool(
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            min_size=1,
            max_size=10
        )
    
    async def close(self) -> None:
        """Закрытие соединения"""
        if self.pool:
            await self.pool.close()
    
    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with self.pool.acquire() as conn:
            # Создание таблиц
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    session_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    context_files TEXT[],
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES sessions(id),
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES sessions(id),
                    message_id INTEGER REFERENCES messages(id),
                    file_type VARCHAR(50) NOT NULL,
                    file_id VARCHAR(255) NOT NULL,
                    file_path VARCHAR(500),
                    file_name VARCHAR(255),
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id SERIAL PRIMARY KEY,
                    attachment_id INTEGER REFERENCES attachments(id),
                    text TEXT NOT NULL,
                    language VARCHAR(10),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES sessions(id),
                    file_path VARCHAR(500) NOT NULL,
                    change_type VARCHAR(50) NOT NULL,
                    old_content TEXT,
                    new_content TEXT,
                    file_hash VARCHAR(64),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Создание индексов
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_session 
                ON file_changes(session_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_path 
                ON file_changes(file_path)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_created 
                ON file_changes(created_at)
            """)
    
    async def ensure_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Создать или обновить пользователя"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO users (telegram_id, username)
                VALUES ($1, $2)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET username = EXCLUDED.username
                RETURNING id, telegram_id, username, created_at
            """, telegram_id, username)
            return dict(row)
    
    async def create_session(
        self,
        user_id: int,
        session_type: str,
        status: str = "active",
        context_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Создать новую сессию"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO sessions (user_id, session_type, status, context_files)
                VALUES ($1, $2, $3, $4)
                RETURNING id, user_id, session_type, status, context_files, created_at, updated_at
            """, user_id, session_type, status, context_files or [])
            return dict(row)
    
    async def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Получить сессию по ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM sessions WHERE id = $1
            """, session_id)
            return dict(row) if row else None
    
    async def get_active_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить активную сессию пользователя"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM sessions 
                WHERE user_id = $1 AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """, user_id)
            return dict(row) if row else None
    
    async def get_user_sessions(
        self,
        user_id: int,
        limit: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список сессий пользователя"""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM sessions WHERE user_id = $1"
            params = [user_id]
            
            if status:
                query += " AND status = $2"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def update_session(
        self,
        session_id: int,
        status: Optional[str] = None,
        context_files: Optional[List[str]] = None
    ) -> None:
        """Обновить сессию"""
        updates = []
        params = []
        param_num = 1
        
        if status:
            updates.append(f"status = ${param_num}")
            params.append(status)
            param_num += 1
        
        if context_files is not None:
            updates.append(f"context_files = ${param_num}")
            params.append(context_files)
            param_num += 1
        
        updates.append(f"updated_at = NOW()")
        params.append(session_id)
        
        async with self.pool.acquire() as conn:
            await conn.execute(f"""
                UPDATE sessions 
                SET {', '.join(updates)}
                WHERE id = ${param_num}
            """, *params)
    
    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str
    ) -> Dict[str, Any]:
        """Добавить сообщение в сессию"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO messages (session_id, role, content)
                VALUES ($1, $2, $3)
                RETURNING id, session_id, role, content, created_at
            """, session_id, role, content)
            return dict(row)
    
    async def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю сообщений сессии"""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM messages WHERE session_id = $1 ORDER BY created_at ASC"
            if limit:
                query += f" LIMIT {limit}"
            rows = await conn.fetch(query, session_id)
            return [dict(row) for row in rows]
    
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
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO attachments 
                (session_id, message_id, file_type, file_id, file_path, file_name, file_size)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, session_id, message_id, file_type, file_id, file_path, 
                          file_name, file_size, created_at
            """, session_id, message_id, file_type, file_id, file_path, file_name, file_size)
            return dict(row)
    
    async def get_session_attachments(self, session_id: int) -> List[Dict[str, Any]]:
        """Получить вложения сессии"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM attachments WHERE session_id = $1 ORDER BY created_at ASC
            """, session_id)
            return [dict(row) for row in rows]
    
    async def add_transcription(
        self,
        attachment_id: int,
        text: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Добавить транскрипцию"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO transcriptions (attachment_id, text, language)
                VALUES ($1, $2, $3)
                RETURNING id, attachment_id, text, language, created_at
            """, attachment_id, text, language)
            return dict(row)
    
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
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO file_changes 
                (session_id, file_path, change_type, old_content, new_content, file_hash)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, session_id, file_path, change_type, old_content, 
                          new_content, file_hash, created_at
            """, session_id, file_path, change_type, old_content, new_content, file_hash)
            return dict(row)
    
    async def get_file_changes(
        self,
        session_id: Optional[int] = None,
        file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю изменений файлов"""
        conditions = []
        params = []
        param_num = 1
        
        if session_id:
            conditions.append(f"session_id = ${param_num}")
            params.append(session_id)
            param_num += 1
        
        if file_path:
            conditions.append(f"file_path = ${param_num}")
            params.append(file_path)
            param_num += 1
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT * FROM file_changes 
                WHERE {where_clause}
                ORDER BY created_at DESC
            """, *params)
            return [dict(row) for row in rows]
    
    async def get_file_change(self, change_id: int) -> Optional[Dict[str, Any]]:
        """Получить конкретное изменение"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM file_changes WHERE id = $1
            """, change_id)
            return dict(row) if row else None

