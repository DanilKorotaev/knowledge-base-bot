"""Persistence for user_notifications."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from kb_app_api.notifications.schema import ensure_notifications_schema
from kb_app_api.timefmt import to_iso_z
from utils.db_helpers import get_db


def _dumps(value: Any) -> str:
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


def _row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "user_id": int(row["user_id"]),
        "kind": str(row.get("kind") or ""),
        "title": str(row.get("title") or ""),
        "body": str(row.get("body") or ""),
        "source_key": row.get("source_key"),
        "session_id": int(row["session_id"]) if row.get("session_id") is not None else None,
        "message_id": int(row["message_id"]) if row.get("message_id") is not None else None,
        "event_id": row.get("event_id"),
        "payload": _loads(row.get("payload_json"), {}),
        "dedupe_key": row.get("dedupe_key"),
        "created_at": to_iso_z(row.get("created_at")),
        "read_at": to_iso_z(row["read_at"]) if row.get("read_at") else None,
    }


async def create_notification(
    *,
    user_id: int,
    kind: str,
    title: str,
    body: str = "",
    source_key: str | None = None,
    session_id: int | None = None,
    message_id: int | None = None,
    event_id: str | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> dict[str, Any] | None:
    """Insert notification; returns row or None if dedupe hit."""
    await ensure_notifications_schema()
    nid = str(uuid.uuid4())
    payload_json = _dumps(payload or {})
    dedupe = (dedupe_key or "").strip() or None
    db = await get_db()

    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if dedupe:
                cur = await conn.execute(
                    "SELECT id FROM user_notifications WHERE user_id=? AND dedupe_key=? LIMIT 1",
                    (user_id, dedupe),
                )
                if await cur.fetchone():
                    return None
            await conn.execute(
                """
                INSERT INTO user_notifications (
                    id, user_id, kind, title, body, source_key,
                    session_id, message_id, event_id, payload_json, dedupe_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nid,
                    user_id,
                    kind,
                    title,
                    body,
                    source_key,
                    session_id,
                    message_id,
                    event_id,
                    payload_json,
                    dedupe,
                ),
            )
            await conn.commit()
            cur = await conn.execute(
                "SELECT * FROM user_notifications WHERE id=? LIMIT 1",
                (nid,),
            )
            row = await cur.fetchone()
            return _row(dict(row)) if row else None

    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        if dedupe:
            existing = await conn.fetchrow(
                "SELECT id FROM user_notifications WHERE user_id=$1 AND dedupe_key=$2 LIMIT 1",
                user_id,
                dedupe,
            )
            if existing:
                return None
        await conn.execute(
            """
            INSERT INTO user_notifications (
                id, user_id, kind, title, body, source_key,
                session_id, message_id, event_id, payload_json, dedupe_key
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            """,
            nid,
            user_id,
            kind,
            title,
            body,
            source_key,
            session_id,
            message_id,
            event_id,
            payload_json,
            dedupe,
        )
        row = await conn.fetchrow(
            "SELECT * FROM user_notifications WHERE id=$1 LIMIT 1",
            nid,
        )
        return _row(dict(row)) if row else None


async def list_notifications(
    user_id: int,
    *,
    limit: int = 50,
    before: str | None = None,
) -> list[dict[str, Any]]:
    await ensure_notifications_schema()
    limit = max(1, min(int(limit), 100))
    db = await get_db()

    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if before:
                cur = await conn.execute(
                    """
                    SELECT * FROM user_notifications
                    WHERE user_id=? AND created_at < (
                        SELECT created_at FROM user_notifications WHERE id=? AND user_id=?
                    )
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user_id, before, user_id, limit),
                )
            else:
                cur = await conn.execute(
                    """
                    SELECT * FROM user_notifications
                    WHERE user_id=?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
            rows = await cur.fetchall()
            return [_row(dict(r)) for r in rows]

    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        if before:
            rows = await conn.fetch(
                """
                SELECT * FROM user_notifications
                WHERE user_id=$1 AND created_at < (
                    SELECT created_at FROM user_notifications WHERE id=$2 AND user_id=$1
                )
                ORDER BY created_at DESC, id DESC
                LIMIT $3
                """,
                user_id,
                before,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT * FROM user_notifications
                WHERE user_id=$1
                ORDER BY created_at DESC, id DESC
                LIMIT $2
                """,
                user_id,
                limit,
            )
        return [_row(dict(r)) for r in rows]


async def unread_count(user_id: int) -> int:
    await ensure_notifications_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) AS c FROM user_notifications WHERE user_id=? AND read_at IS NULL",
                (user_id,),
            )
            row = await cur.fetchone()
            return int(row[0]) if row else 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COUNT(*) FROM user_notifications WHERE user_id=$1 AND read_at IS NULL",
            user_id,
        )
        return int(val or 0)


async def mark_read(user_id: int, notification_id: str) -> bool:
    await ensure_notifications_schema()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                """
                UPDATE user_notifications
                SET read_at=COALESCE(read_at, ?)
                WHERE id=? AND user_id=?
                """,
                (now.isoformat(sep=" "), notification_id, user_id),
            )
            await conn.commit()
            return cur.rowcount > 0
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_notifications
            SET read_at=COALESCE(read_at, NOW())
            WHERE id=$1 AND user_id=$2
            """,
            notification_id,
            user_id,
        )
        return result != "UPDATE 0"


async def mark_all_read(user_id: int) -> int:
    await ensure_notifications_schema()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            cur = await conn.execute(
                """
                UPDATE user_notifications
                SET read_at=?
                WHERE user_id=? AND read_at IS NULL
                """,
                (now.isoformat(sep=" "), user_id),
            )
            await conn.commit()
            return int(cur.rowcount or 0)
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_notifications
            SET read_at=NOW()
            WHERE user_id=$1 AND read_at IS NULL
            """,
            user_id,
        )
        # asyncpg returns "UPDATE N"
        try:
            return int(str(result).split()[-1])
        except (TypeError, ValueError, IndexError):
            return 0
