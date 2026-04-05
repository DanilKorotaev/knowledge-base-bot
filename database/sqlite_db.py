"""
Реализация работы с SQLite (для локальной разработки)
"""
import aiosqlite
from typing import Optional, List, Dict, Any
from .base import DatabaseInterface
from config import config


class SQLiteDatabase(DatabaseInterface):
    """Реализация работы с SQLite"""
    
    def __init__(self):
        self.db_path: str = config.DB_FILE or "bot.db"
    
    async def connect(self) -> None:
        """Подключение к базе данных (для SQLite не требуется)"""
        pass
    
    async def close(self) -> None:
        """Закрытие соединения (для SQLite не требуется)"""
        pass
    
    async def init_db(self) -> None:
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Создание таблиц
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    is_allowed INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Миграция: добавить поля is_allowed и is_admin, если их нет
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = {row[1] for row in await cursor.fetchall()}
            
            if 'is_allowed' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN is_allowed INTEGER DEFAULT 0")
            
            if 'is_admin' not in columns:
                await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            
            await db.commit()
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    session_type TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    context_files TEXT,
                    cursor_chat_id TEXT,
                    display_title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Миграция: добавить поле cursor_chat_id, если его нет
            cursor = await db.execute("PRAGMA table_info(sessions)")
            session_columns = {row[1] for row in await cursor.fetchall()}
            
            if 'cursor_chat_id' not in session_columns:
                await db.execute("ALTER TABLE sessions ADD COLUMN cursor_chat_id TEXT")
            
            if 'display_title' not in session_columns:
                await db.execute("ALTER TABLE sessions ADD COLUMN display_title TEXT")
            
            await db.commit()
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    message_id INTEGER REFERENCES messages(id),
                    file_type TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    file_path TEXT,
                    file_name TEXT,
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attachment_id INTEGER REFERENCES attachments(id),
                    text TEXT NOT NULL,
                    language TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER REFERENCES sessions(id),
                    file_path TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    old_content TEXT,
                    new_content TEXT,
                    file_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Создание индексов
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_session 
                ON file_changes(session_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_path 
                ON file_changes(file_path)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_changes_created 
                ON file_changes(created_at)
            """)
            
            await db.commit()
    
    async def ensure_user(self, telegram_id: int, username: Optional[str] = None) -> Dict[str, Any]:
        """Создать или обновить пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сначала попробуем вставить, если пользователя нет
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, username)
                VALUES (?, ?)
            """, (telegram_id, username))
            
            # Затем обновим username, если пользователь уже существует
            if username:
                await db.execute("""
                    UPDATE users SET username = ? WHERE telegram_id = ?
                """, (username, telegram_id))
            
            await db.commit()
            
            cursor = await db.execute("""
                SELECT id, telegram_id, username, is_allowed, is_admin, created_at 
                FROM users WHERE telegram_id = ?
            """, (telegram_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "telegram_id": row[1],
                "username": row[2],
                "is_allowed": bool(row[3]) if len(row) > 3 else False,
                "is_admin": bool(row[4]) if len(row) > 4 else False,
                "created_at": row[5] if len(row) > 5 else row[3]
            }
    
    async def create_session(
        self,
        user_id: int,
        session_type: str,
        status: str = "active",
        context_files: Optional[List[str]] = None,
        display_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создать новую сессию"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO sessions (user_id, session_type, status, context_files, display_title)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, session_type, status, json.dumps(context_files or []), display_title))
            await db.commit()
            
            session_id = cursor.lastrowid
            cursor = await db.execute("""
                SELECT id, user_id, session_type, status, context_files, cursor_chat_id, display_title, created_at, updated_at
                FROM sessions WHERE id = ?
            """, (session_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "user_id": row[1],
                "session_type": row[2],
                "status": row[3],
                "context_files": json.loads(row[4]) if row[4] else [],
                "cursor_chat_id": row[5],
                "display_title": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }
    
    async def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Получить сессию по ID"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, user_id, session_type, status, context_files, cursor_chat_id, display_title, created_at, updated_at
                FROM sessions WHERE id = ?
            """, (session_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "id": row[0],
                "user_id": row[1],
                "session_type": row[2],
                "status": row[3],
                "context_files": json.loads(row[4]) if row[4] else [],
                "cursor_chat_id": row[5],
                "display_title": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }
    
    async def get_active_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить активную сессию пользователя"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, user_id, session_type, status, context_files, cursor_chat_id, display_title, created_at, updated_at
                FROM sessions 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "id": row[0],
                "user_id": row[1],
                "session_type": row[2],
                "status": row[3],
                "context_files": json.loads(row[4]) if row[4] else [],
                "cursor_chat_id": row[5],
                "display_title": row[6],
                "created_at": row[7],
                "updated_at": row[8]
            }
    
    async def get_user_sessions(
        self,
        user_id: int,
        limit: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить список сессий пользователя"""
        import json
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT id, user_id, session_type, status, context_files, cursor_chat_id, display_title, created_at, updated_at FROM sessions WHERE user_id = ?"
            params = [user_id]
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            
            sessions = []
            for row in rows:
                sessions.append({
                    "id": row[0],
                    "user_id": row[1],
                    "session_type": row[2],
                    "status": row[3],
                    "context_files": json.loads(row[4]) if row[4] else [],
                    "cursor_chat_id": row[5],
                    "display_title": row[6],
                    "created_at": row[7],
                    "updated_at": row[8]
                })
            
            return sessions
    
    async def update_session(
        self,
        session_id: int,
        status: Optional[str] = None,
        context_files: Optional[List[str]] = None,
        cursor_chat_id: Optional[str] = None,
        display_title: Optional[str] = None,
    ) -> None:
        """Обновить сессию"""
        import json
        updates = []
        params = []
        
        if status:
            updates.append("status = ?")
            params.append(status)
        
        if context_files is not None:
            updates.append("context_files = ?")
            params.append(json.dumps(context_files))
        
        if cursor_chat_id is not None:
            updates.append("cursor_chat_id = ?")
            # Пустая строка означает сброс cursor_chat_id
            params.append(cursor_chat_id if cursor_chat_id else None)
        
        if display_title is not None:
            updates.append("display_title = ?")
            params.append(display_title)
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(session_id)
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                UPDATE sessions 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            await db.commit()
    
    async def add_message(
        self,
        session_id: int,
        role: str,
        content: str
    ) -> Dict[str, Any]:
        """Добавить сообщение в сессию"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO messages (session_id, role, content)
                VALUES (?, ?, ?)
            """, (session_id, role, content))
            message_id = cursor.lastrowid
            await db.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,),
            )
            await db.commit()
            cursor = await db.execute("""
                SELECT id, session_id, role, content, created_at
                FROM messages WHERE id = ?
            """, (message_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "session_id": row[1],
                "role": row[2],
                "content": row[3],
                "created_at": row[4]
            }
    
    async def get_session_messages(
        self,
        session_id: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю сообщений сессии"""
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC"
            if limit:
                query += f" LIMIT {limit}"
            
            cursor = await db.execute(query, (session_id,))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "role": row[2],
                    "content": row[3],
                    "created_at": row[4]
                }
                for row in rows
            ]
    
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO attachments 
                (session_id, message_id, file_type, file_id, file_path, file_name, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, message_id, file_type, file_id, file_path, file_name, file_size))
            await db.commit()
            
            attachment_id = cursor.lastrowid
            cursor = await db.execute("""
                SELECT id, session_id, message_id, file_type, file_id, file_path, 
                       file_name, file_size, created_at
                FROM attachments WHERE id = ?
            """, (attachment_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "session_id": row[1],
                "message_id": row[2],
                "file_type": row[3],
                "file_id": row[4],
                "file_path": row[5],
                "file_name": row[6],
                "file_size": row[7],
                "created_at": row[8]
            }
    
    async def get_session_attachments(self, session_id: int) -> List[Dict[str, Any]]:
        """Получить вложения сессии"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT * FROM attachments WHERE session_id = ? ORDER BY created_at ASC
            """, (session_id,))
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "message_id": row[2],
                    "file_type": row[3],
                    "file_id": row[4],
                    "file_path": row[5],
                    "file_name": row[6],
                    "file_size": row[7],
                    "created_at": row[8]
                }
                for row in rows
            ]
    
    async def add_transcription(
        self,
        attachment_id: int,
        text: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Добавить транскрипцию"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO transcriptions (attachment_id, text, language)
                VALUES (?, ?, ?)
            """, (attachment_id, text, language))
            await db.commit()
            
            transcription_id = cursor.lastrowid
            cursor = await db.execute("""
                SELECT id, attachment_id, text, language, created_at
                FROM transcriptions WHERE id = ?
            """, (transcription_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "attachment_id": row[1],
                "text": row[2],
                "language": row[3],
                "created_at": row[4]
            }
    
    async def get_last_voice_attachment(
        self,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить последнее голосовое сообщение пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT a.id, a.session_id, a.message_id, a.file_type, a.file_id, 
                       a.file_path, a.file_name, a.file_size, a.created_at
                FROM attachments a
                JOIN sessions s ON a.session_id = s.id
                WHERE s.user_id = ? AND a.file_type = 'voice'
                ORDER BY a.created_at DESC
                LIMIT 1
            """, (user_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "session_id": row[1],
                "message_id": row[2],
                "file_type": row[3],
                "file_id": row[4],
                "file_path": row[5],
                "file_name": row[6],
                "file_size": row[7],
                "created_at": row[8]
            }
    
    async def get_transcription(
        self,
        attachment_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получить транскрипцию по ID вложения"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, attachment_id, text, language, created_at
                FROM transcriptions WHERE attachment_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (attachment_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "attachment_id": row[1],
                "text": row[2],
                "language": row[3],
                "created_at": row[4]
            }
    
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
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO file_changes 
                (session_id, file_path, change_type, old_content, new_content, file_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_id, file_path, change_type, old_content, new_content, file_hash))
            await db.commit()
            
            change_id = cursor.lastrowid
            cursor = await db.execute("""
                SELECT id, session_id, file_path, change_type, old_content, 
                       new_content, file_hash, created_at
                FROM file_changes WHERE id = ?
            """, (change_id,))
            row = await cursor.fetchone()
            return {
                "id": row[0],
                "session_id": row[1],
                "file_path": row[2],
                "change_type": row[3],
                "old_content": row[4],
                "new_content": row[5],
                "file_hash": row[6],
                "created_at": row[7]
            }
    
    async def get_file_changes(
        self,
        session_id: Optional[int] = None,
        file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Получить историю изменений файлов"""
        conditions = []
        params = []
        
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        
        if file_path:
            conditions.append("file_path = ?")
            params.append(file_path)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"""
                SELECT * FROM file_changes 
                WHERE {where_clause}
                ORDER BY created_at DESC
            """, params)
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "file_path": row[2],
                    "change_type": row[3],
                    "old_content": row[4],
                    "new_content": row[5],
                    "file_hash": row[6],
                    "created_at": row[7]
                }
                for row in rows
            ]
    
    async def get_file_change(self, change_id: int) -> Optional[Dict[str, Any]]:
        """Получить конкретное изменение"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT * FROM file_changes WHERE id = ?
            """, (change_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            
            return {
                "id": row[0],
                "session_id": row[1],
                "file_path": row[2],
                "change_type": row[3],
                "old_content": row[4],
                "new_content": row[5],
                "file_hash": row[6],
                "created_at": row[7]
            }
    
    async def is_user_allowed(self, telegram_id: int) -> bool:
        """Проверить, разрешен ли доступ пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT is_allowed FROM users WHERE telegram_id = ?
            """, (telegram_id,))
            row = await cursor.fetchone()
            return bool(row[0]) if row else False
    
    async def is_user_admin(self, telegram_id: int) -> bool:
        """Проверить, является ли пользователь администратором"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT is_admin FROM users WHERE telegram_id = ?
            """, (telegram_id,))
            row = await cursor.fetchone()
            return bool(row[0]) if row else False
    
    async def allow_user(self, telegram_id: int) -> None:
        """Разрешить доступ пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            # Создать пользователя, если его нет
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, is_allowed)
                VALUES (?, 1)
            """, (telegram_id,))
            await db.execute("""
                UPDATE users SET is_allowed = 1 WHERE telegram_id = ?
            """, (telegram_id,))
            await db.commit()
    
    async def disallow_user(self, telegram_id: int) -> None:
        """Запретить доступ пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users SET is_allowed = 0 WHERE telegram_id = ?
            """, (telegram_id,))
            await db.commit()
    
    async def set_user_admin(self, telegram_id: int, is_admin: bool) -> None:
        """Установить права администратора пользователю"""
        async with aiosqlite.connect(self.db_path) as db:
            # Создать пользователя, если его нет, и установить права
            await db.execute("""
                INSERT OR IGNORE INTO users (telegram_id, is_admin, is_allowed)
                VALUES (?, ?, 1)
            """, (telegram_id, 1 if is_admin else 0))
            await db.execute("""
                UPDATE users SET is_admin = ?, is_allowed = 1 WHERE telegram_id = ?
            """, (1 if is_admin else 0, telegram_id))
            await db.commit()
    
    async def get_allowed_users(self) -> List[Dict[str, Any]]:
        """Получить список всех разрешенных пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT id, telegram_id, username, is_allowed, is_admin, created_at
                FROM users
                WHERE is_allowed = 1
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "telegram_id": row[1],
                    "username": row[2],
                    "is_allowed": bool(row[3]),
                    "is_admin": bool(row[4]),
                    "created_at": row[5]
                }
                for row in rows
            ]

