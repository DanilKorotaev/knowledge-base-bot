"""Idempotent DDL for ingress tables + messages.metadata_json."""
from __future__ import annotations

import logging

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)

_SCHEMA_READY = False

_SQLITE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS ingress_adapters (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        participant_key TEXT NOT NULL,
        avatar_asset_id TEXT,
        config_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_tokens (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        token_prefix TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        channel_id TEXT NOT NULL DEFAULT 'default',
        adapter_key TEXT,
        allowed_sources_json TEXT,
        allow_enqueue_agent INTEGER NOT NULL DEFAULT 0,
        allow_script INTEGER NOT NULL DEFAULT 0,
        agent_runtime TEXT NOT NULL DEFAULT 'none',
        agent_prompt_profile TEXT NOT NULL DEFAULT 'untrusted_ingress',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_session_bindings (
        user_id INTEGER NOT NULL,
        binding_key TEXT NOT NULL,
        session_id INTEGER NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, binding_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_rules (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        priority INTEGER NOT NULL DEFAULT 100,
        enabled INTEGER NOT NULL DEFAULT 1,
        match_json TEXT NOT NULL DEFAULT '{}',
        extract_json TEXT NOT NULL DEFAULT '{}',
        action_json TEXT NOT NULL DEFAULT '{}',
        label TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_scripts (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        command_json TEXT NOT NULL DEFAULT '{}',
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_events (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token_id TEXT,
        channel_id TEXT NOT NULL DEFAULT 'default',
        adapter_key TEXT,
        source TEXT NOT NULL DEFAULT '',
        event_type TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        dedupe_key TEXT,
        status TEXT NOT NULL DEFAULT 'received',
        envelope_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, dedupe_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_avatar_assets (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        participant_key TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'image/png',
        file_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, participant_key)
    )
    """,
]

_PG_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS ingress_adapters (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL,
        participant_key TEXT NOT NULL,
        avatar_asset_id TEXT,
        config_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_tokens (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        token_prefix TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        channel_id TEXT NOT NULL DEFAULT 'default',
        adapter_key TEXT,
        allowed_sources_json TEXT,
        allow_enqueue_agent BOOLEAN NOT NULL DEFAULT FALSE,
        allow_script BOOLEAN NOT NULL DEFAULT FALSE,
        agent_runtime TEXT NOT NULL DEFAULT 'none',
        agent_prompt_profile TEXT NOT NULL DEFAULT 'untrusted_ingress',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        revoked_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_session_bindings (
        user_id INTEGER NOT NULL,
        binding_key TEXT NOT NULL,
        session_id INTEGER NOT NULL,
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (user_id, binding_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_rules (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        priority INTEGER NOT NULL DEFAULT 100,
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        match_json TEXT NOT NULL DEFAULT '{}',
        extract_json TEXT NOT NULL DEFAULT '{}',
        action_json TEXT NOT NULL DEFAULT '{}',
        label TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_scripts (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        key TEXT NOT NULL,
        label TEXT NOT NULL DEFAULT '',
        command_json TEXT NOT NULL DEFAULT '{}',
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_events (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token_id TEXT,
        channel_id TEXT NOT NULL DEFAULT 'default',
        adapter_key TEXT,
        source TEXT NOT NULL DEFAULT '',
        event_type TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        dedupe_key TEXT,
        status TEXT NOT NULL DEFAULT 'received',
        envelope_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT,
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, dedupe_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingress_avatar_assets (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        participant_key TEXT NOT NULL,
        content_type TEXT NOT NULL DEFAULT 'image/png',
        file_name TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(user_id, participant_key)
    )
    """,
]


async def ensure_ingress_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            for ddl in _SQLITE_TABLES:
                await conn.execute(ddl)
            cols = {
                row[1]
                for row in await (
                    await conn.execute("PRAGMA table_info(messages)")
                ).fetchall()
            }
            if "metadata_json" not in cols:
                await conn.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT")
            tok_cols = {
                row[1]
                for row in await (
                    await conn.execute("PRAGMA table_info(ingress_tokens)")
                ).fetchall()
            }
            if "description" not in tok_cols:
                await conn.execute(
                    "ALTER TABLE ingress_tokens ADD COLUMN description TEXT NOT NULL DEFAULT ''"
                )
            await conn.commit()
    elif isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            for ddl in _PG_TABLES:
                await conn.execute(ddl)
            exists = await conn.fetchval(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name='messages' AND column_name='metadata_json'
                """
            )
            if not exists:
                await conn.execute("ALTER TABLE messages ADD COLUMN metadata_json TEXT")
            await conn.execute(
                "ALTER TABLE ingress_tokens ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''"
            )
    else:
        logger.warning("ingress schema: unknown db type %s", type(db))
        return
    _SCHEMA_READY = True
    logger.info("ingress schema ready")
