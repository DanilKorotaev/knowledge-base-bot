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
                    is_allowed BOOLEAN DEFAULT FALSE,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Миграция: добавить поля is_allowed и is_admin, если их нет
            # Проверяем существование колонок
            column_check = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name IN ('is_allowed', 'is_admin')
            """)
            existing_columns = {row['column_name'] for row in column_check}
            
            if 'is_allowed' not in existing_columns:
                await conn.execute("""
                    ALTER TABLE users ADD COLUMN is_allowed BOOLEAN DEFAULT FALSE
                """)
            
            if 'is_admin' not in existing_columns:
                await conn.execute("""
                    ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE
                """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    session_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'active',
                    context_files TEXT[],
                    cursor_chat_id VARCHAR(255),
                    display_title VARCHAR(500),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # Миграция: добавить поле cursor_chat_id, если его нет
            session_column_check = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='sessions' AND column_name = 'cursor_chat_id'
            """)
            if not session_column_check:
                await conn.execute("""
                    ALTER TABLE sessions ADD COLUMN cursor_chat_id VARCHAR(255)
                """)
            
            session_title_check = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='sessions' AND column_name = 'display_title'
            """)
            if not session_title_check:
                await conn.execute("""
                    ALTER TABLE sessions ADD COLUMN display_title VARCHAR(500)
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

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_devices (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    device_token VARCHAR(512) NOT NULL,
                    platform VARCHAR(20) NOT NULL DEFAULT 'ios',
                    apns_environment VARCHAR(20) NOT NULL DEFAULT 'production',
                    app_version VARCHAR(50),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE (user_id, device_token)
                )
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_devices_user_id
                ON user_devices(user_id)
            """)
    
    async def ensure_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Создать или обновить пользователя"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO users (telegram_id, username)
                VALUES ($1, $2)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET username = EXCLUDED.username
                RETURNING id, telegram_id, username, is_allowed, is_admin, created_at
            """, telegram_id, username)
            return dict(row)
    
    async def create_session(
        self,
        user_id: int,
        session_type: str,
        status: str = "active",
        context_files: Optional[List[str]] = None,
        display_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать новую сессию"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO sessions (user_id, session_type, status, context_files, display_title)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
            """, user_id, session_type, status, context_files or [], display_title)
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
        context_files: Optional[List[str]] = None,
        cursor_chat_id: Optional[str] = None,
        display_title: Optional[str] = None,
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
        
        if cursor_chat_id is not None:
            updates.append(f"cursor_chat_id = ${param_num}")
            # Пустая строка означает сброс cursor_chat_id
            params.append(cursor_chat_id if cursor_chat_id else None)
            param_num += 1
        
        if display_title is not None:
            updates.append(f"display_title = ${param_num}")
            params.append(display_title)
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
            await conn.execute(
                "UPDATE sessions SET updated_at = NOW() WHERE id = $1",
                session_id,
            )
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

    async def get_session_messages_window(
        self,
        session_id: int,
        *,
        limit: int,
        before_id: Optional[int] = None,
    ) -> tuple[list[dict[str, Any]], int, bool]:
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM messages WHERE session_id = $1",
                session_id,
            )
            total = int(total or 0)

            if before_id is not None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM messages
                    WHERE session_id = $1 AND id < $2
                    ORDER BY id DESC LIMIT $3
                    """,
                    session_id,
                    before_id,
                    limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM messages
                    WHERE session_id = $1
                    ORDER BY id DESC LIMIT $2
                    """,
                    session_id,
                    limit,
                )
            messages = [dict(row) for row in reversed(rows)]

            has_more = False
            if messages:
                oldest_id = messages[0]["id"]
                older_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM messages WHERE session_id = $1 AND id < $2",
                    session_id,
                    oldest_id,
                )
                has_more = int(older_count or 0) > 0

            return messages, total, has_more
    
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
    
    async def get_last_voice_attachment(
        self,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить последнее голосовое сообщение пользователя"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT a.id, a.session_id, a.message_id, a.file_type, a.file_id, 
                       a.file_path, a.file_name, a.file_size, a.created_at
                FROM attachments a
                JOIN sessions s ON a.session_id = s.id
                WHERE s.user_id = $1 AND a.file_type = 'voice'
                ORDER BY a.created_at DESC
                LIMIT 1
            """, user_id)
            return dict(row) if row else None
    
    async def get_transcription(
        self,
        attachment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить транскрипцию по ID вложения"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, attachment_id, text, language, created_at
                FROM transcriptions WHERE attachment_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, attachment_id)
            return dict(row) if row else None
    
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
    
    async def is_user_allowed(self, telegram_id: int) -> bool:
        """Проверить, разрешен ли доступ пользователю"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT is_allowed FROM users WHERE telegram_id = $1
            """, telegram_id)
            return row['is_allowed'] if row else False
    
    async def is_user_admin(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT is_admin FROM users WHERE telegram_id = $1
            """, telegram_id)
            return row['is_admin'] if row else False
    
    async def allow_user(self, telegram_id: int) -> None:
        """Разрешить доступ пользователю"""
        async with self.pool.acquire() as conn:
            # Создать пользователя, если его нет
            await conn.execute("""
                INSERT INTO users (telegram_id, is_allowed)
                VALUES ($1, TRUE)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET is_allowed = TRUE
            """, telegram_id)
    
    async def disallow_user(self, telegram_id: int) -> None:
        """Запретить доступ пользователю"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET is_allowed = FALSE WHERE telegram_id = $1
            """, telegram_id)
    
    async def set_user_admin(self, telegram_id: int, is_admin: bool) -> None:
        """Установить права администратора пользователю"""
        async with self.pool.acquire() as conn:
            # Создать пользователя, если его нет, и установить права
            await conn.execute("""
                INSERT INTO users (telegram_id, is_admin, is_allowed)
                VALUES ($1, $2, TRUE)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET is_admin = $2, is_allowed = TRUE
            """, telegram_id, is_admin)
    
    async def get_allowed_users(self) -> List[Dict[str, Any]]:
        """Получить список всех разрешенных пользователей"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, telegram_id, username, is_allowed, is_admin, created_at
                FROM users
                WHERE is_allowed = TRUE
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in rows]

    async def upsert_user_device(
        self,
        user_id: int,
        device_token: str,
        platform: str,
        apns_environment: str,
        app_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_devices
                    (user_id, device_token, platform, apns_environment, app_version, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (user_id, device_token)
                DO UPDATE SET
                    platform = EXCLUDED.platform,
                    apns_environment = EXCLUDED.apns_environment,
                    app_version = EXCLUDED.app_version,
                    updated_at = NOW()
                RETURNING id, user_id, device_token, platform, apns_environment, app_version, updated_at
                """,
                user_id,
                device_token,
                platform,
                apns_environment,
                app_version,
            )
            return dict(row)

    async def delete_user_device(self, user_id: int, device_token: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM user_devices WHERE user_id = $1 AND device_token = $2",
                user_id,
                device_token,
            )

    async def list_user_devices(self, user_id: int) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, user_id, device_token, platform, apns_environment, app_version, updated_at
                FROM user_devices
                WHERE user_id = $1
                ORDER BY updated_at DESC
                """,
                user_id,
            )
            return [dict(row) for row in rows]

