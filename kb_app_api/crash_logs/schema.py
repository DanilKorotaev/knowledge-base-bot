"""DDL for crash-log links and the accept_crash_logs switch."""
from __future__ import annotations

import logging

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)

_READY = False

_SQLITE = [
    """
    CREATE TABLE IF NOT EXISTS crash_log_links (
        user_id INTEGER NOT NULL,
        log_session TEXT NOT NULL,
        app_version TEXT NOT NULL DEFAULT '',
        app_build TEXT NOT NULL DEFAULT '',
        file_name TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        chat_session_id INTEGER,
        crash_event_id TEXT,
        logs_notified INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, log_session)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]

_PG = [
    """
    CREATE TABLE IF NOT EXISTS crash_log_links (
        user_id INTEGER NOT NULL,
        log_session TEXT NOT NULL,
        app_version TEXT NOT NULL DEFAULT '',
        app_build TEXT NOT NULL DEFAULT '',
        file_name TEXT,
        size_bytes INTEGER NOT NULL DEFAULT 0,
        chat_session_id INTEGER,
        crash_event_id TEXT,
        logs_notified INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (user_id, log_session)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
]


async def ensure_crash_log_schema() -> None:
    global _READY
    if _READY:
        return
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            for ddl in _SQLITE:
                await conn.execute(ddl)
            await conn.commit()
    elif isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            for ddl in _PG:
                await conn.execute(ddl)
    else:
        logger.warning("crash log schema: unknown db type %s", type(db))
        return
    _READY = True
