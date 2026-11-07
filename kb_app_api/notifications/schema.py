"""Idempotent DDL for user_notifications."""
from __future__ import annotations

import logging

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)

# Track which DB instance already has DDL applied (tests swap SQLite files).
_SCHEMA_READY_FOR: str | None = None

_SQLITE = """
CREATE TABLE IF NOT EXISTS user_notifications (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    source_key TEXT,
    session_id INTEGER,
    message_id INTEGER,
    event_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP
)
"""

_PG = """
CREATE TABLE IF NOT EXISTS user_notifications (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    source_key TEXT,
    session_id INTEGER,
    message_id INTEGER,
    event_id TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ
)
"""


async def ensure_notifications_schema() -> None:
    global _SCHEMA_READY_FOR
    db = await get_db()
    ready_key = (
        f"sqlite:{db.db_path}"
        if isinstance(db, SQLiteDatabase)
        else f"pg:{id(getattr(db, 'pool', None))}"
    )
    if _SCHEMA_READY_FOR == ready_key:
        return
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(_SQLITE)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_notifications_user_created "
                "ON user_notifications(user_id, created_at DESC)"
            )
            # Partial unique indexes vary by SQLite build; dedupe is enforced in store.
            await conn.commit()
    else:
        assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
        async with db.pool.acquire() as conn:
            await conn.execute(_PG)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_notifications_user_created "
                "ON user_notifications(user_id, created_at DESC)"
            )
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_notifications_dedupe "
                "ON user_notifications(user_id, dedupe_key) "
                "WHERE dedupe_key IS NOT NULL AND dedupe_key <> ''"
            )
    _SCHEMA_READY_FOR = ready_key
    logger.info("notifications schema ready")
