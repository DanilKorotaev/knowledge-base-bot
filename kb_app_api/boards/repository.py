"""Persist board definitions in the app DB (paths live in definition JSON)."""
from __future__ import annotations

import json
import logging
from typing import Any

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

from kb_app_api.boards.seed import DEFAULT_BOARDS

logger = logging.getLogger(__name__)

_SCHEMA_READY = False


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(raw: Any, default: Any = None) -> Any:
    if raw is None or raw == "":
        return default
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _row_to_board(row: dict[str, Any]) -> dict[str, Any]:
    enabled = row.get("enabled")
    return {
        "id": str(row["id"]),
        "user_id": row.get("user_id"),
        "title": str(row.get("title") or row["id"]),
        "subtitle": row.get("subtitle"),
        "icon": row.get("icon"),
        "kind": str(row.get("kind") or "cached_view"),
        "sort_order": int(row.get("sort_order") or 0),
        "enabled": bool(enabled) if not isinstance(enabled, int) else bool(enabled),
        "definition": _loads(row.get("definition_json"), {}),
        "list_cell": _loads(row.get("list_cell_json")),
        "rendered_document": _loads(row.get("rendered_document_json")),
        "rendered_at": row.get("rendered_at"),
    }


async def ensure_boards_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_app_boards (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    icon TEXT,
                    kind TEXT NOT NULL DEFAULT 'cached_view',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    definition_json TEXT NOT NULL DEFAULT '{}',
                    list_cell_json TEXT,
                    rendered_document_json TEXT,
                    rendered_at TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await conn.commit()
    elif isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_app_boards (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    icon TEXT,
                    kind TEXT NOT NULL DEFAULT 'cached_view',
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    enabled BOOLEAN NOT NULL DEFAULT TRUE,
                    definition_json TEXT NOT NULL DEFAULT '{}',
                    list_cell_json TEXT,
                    rendered_document_json TEXT,
                    rendered_at TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
    else:
        raise RuntimeError(f"unsupported db type for boards: {type(db)}")
    await seed_default_boards_if_empty()
    _SCHEMA_READY = True


async def seed_default_boards_if_empty() -> None:
    existing = await list_board_rows(include_disabled=True)
    existing_ids = {b["id"] for b in existing}
    for seed in DEFAULT_BOARDS:
        if seed["id"] in existing_ids:
            continue
        await upsert_board_row(seed)
        logger.info("seeded board %s", seed["id"])


async def list_board_rows(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if include_disabled:
                cursor = await conn.execute(
                    "SELECT * FROM kb_app_boards ORDER BY sort_order ASC, id ASC"
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM kb_app_boards WHERE enabled = 1 ORDER BY sort_order ASC, id ASC"
                )
            rows = await cursor.fetchall()
            return [_row_to_board(dict(r)) for r in rows]
    if isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            if include_disabled:
                rows = await conn.fetch("SELECT * FROM kb_app_boards ORDER BY sort_order ASC, id ASC")
            else:
                rows = await conn.fetch(
                    "SELECT * FROM kb_app_boards WHERE enabled = TRUE ORDER BY sort_order ASC, id ASC"
                )
            return [_row_to_board(dict(r)) for r in rows]
    return []


async def get_board_row(board_id: str) -> dict[str, Any] | None:
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM kb_app_boards WHERE id = ?", (board_id,))
            row = await cursor.fetchone()
            return _row_to_board(dict(row)) if row else None
    if isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM kb_app_boards WHERE id = $1", board_id)
            return _row_to_board(dict(row)) if row else None
    return None


async def upsert_board_row(payload: dict[str, Any]) -> None:
    db = await get_db()
    board_id = str(payload["id"])
    title = str(payload.get("title") or board_id)
    subtitle = payload.get("subtitle")
    icon = payload.get("icon")
    kind = str(payload.get("kind") or "cached_view")
    sort_order = int(payload.get("sort_order") or 0)
    enabled = 1 if payload.get("enabled", True) else 0
    definition_json = _dumps(payload.get("definition") or {})
    list_cell_json = _dumps(payload.get("list_cell"))
    rendered_document_json = _dumps(payload.get("rendered_document"))
    rendered_at = payload.get("rendered_at")

    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(
                """
                INSERT INTO kb_app_boards (
                    id, title, subtitle, icon, kind, sort_order, enabled,
                    definition_json, list_cell_json, rendered_document_json, rendered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    subtitle=excluded.subtitle,
                    icon=excluded.icon,
                    kind=excluded.kind,
                    sort_order=excluded.sort_order,
                    enabled=excluded.enabled,
                    definition_json=excluded.definition_json,
                    list_cell_json=COALESCE(excluded.list_cell_json, kb_app_boards.list_cell_json),
                    rendered_document_json=COALESCE(excluded.rendered_document_json, kb_app_boards.rendered_document_json),
                    rendered_at=COALESCE(excluded.rendered_at, kb_app_boards.rendered_at),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    board_id,
                    title,
                    subtitle,
                    icon,
                    kind,
                    sort_order,
                    enabled,
                    definition_json,
                    list_cell_json,
                    rendered_document_json,
                    rendered_at,
                ),
            )
            await conn.commit()
        return

    if isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO kb_app_boards (
                    id, title, subtitle, icon, kind, sort_order, enabled,
                    definition_json, list_cell_json, rendered_document_json, rendered_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title,
                    subtitle=EXCLUDED.subtitle,
                    icon=EXCLUDED.icon,
                    kind=EXCLUDED.kind,
                    sort_order=EXCLUDED.sort_order,
                    enabled=EXCLUDED.enabled,
                    definition_json=EXCLUDED.definition_json,
                    list_cell_json=COALESCE(EXCLUDED.list_cell_json, kb_app_boards.list_cell_json),
                    rendered_document_json=COALESCE(EXCLUDED.rendered_document_json, kb_app_boards.rendered_document_json),
                    rendered_at=COALESCE(EXCLUDED.rendered_at, kb_app_boards.rendered_at),
                    updated_at=NOW()
                """,
                board_id,
                title,
                subtitle,
                icon,
                kind,
                sort_order,
                bool(enabled),
                definition_json,
                list_cell_json,
                rendered_document_json,
                rendered_at,
            )


async def delete_board_row(board_id: str) -> bool:
    """Remove a board row. Returns True if a row was deleted."""
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cursor = await conn.execute("DELETE FROM kb_app_boards WHERE id = ?", (board_id,))
            await conn.commit()
            return cursor.rowcount > 0
    if isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM kb_app_boards WHERE id = $1", board_id)
            # asyncpg: "DELETE N"
            try:
                return int(str(result).split()[-1]) > 0
            except (ValueError, IndexError):
                return False
    return False
