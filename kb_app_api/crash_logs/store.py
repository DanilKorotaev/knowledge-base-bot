"""Store crash log files outside the vault and remember whether the report arrived."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

from kb_app_api.crash_logs.schema import ensure_crash_log_schema

_SESSION_RE = re.compile(r"^[A-Za-z0-9-]{8,80}$")
_ACCEPT_KEY = "accept_crash_logs"
MAX_BYTES = 4 * 1024 * 1024


def crash_log_root() -> Path:
    raw = os.getenv("KB_CRASH_LOG_DIR")
    if raw:
        return Path(raw)
    return Path.home() / "Library" / "Application Support" / "kb-app-api" / "crash-logs"


def valid_log_session(value: str) -> bool:
    return bool(_SESSION_RE.fullmatch(value or ""))


def _placeholders(sql: str, postgres: bool) -> str:
    if not postgres:
        return sql
    out: list[str] = []
    index = 0
    for char in sql:
        if char == "?":
            index += 1
            out.append(f"${index}")
        else:
            out.append(char)
    return "".join(out)


async def _fetchone(sql: str, args: tuple[Any, ...]) -> dict[str, Any] | None:
    await ensure_crash_log_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, args)
            row = await cursor.fetchone()
            return dict(row) if row else None
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        row = await conn.fetchrow(_placeholders(sql, True), *args)
        return dict(row) if row else None


async def _execute(sql: str, args: tuple[Any, ...]) -> None:
    await ensure_crash_log_schema()
    db = await get_db()
    if isinstance(db, SQLiteDatabase):
        import aiosqlite

        async with aiosqlite.connect(db.db_path) as conn:
            await conn.execute(sql, args)
            await conn.commit()
        return
    assert isinstance(db, PostgreSQLDatabase) and db.pool is not None
    async with db.pool.acquire() as conn:
        await conn.execute(_placeholders(sql, True), *args)


async def accept_crash_logs() -> bool:
    row = await _fetchone("SELECT value FROM app_settings WHERE key = ?", (_ACCEPT_KEY,))
    if not row:
        return True
    return str(row["value"]).lower() not in ("0", "false", "no")


async def set_accept_crash_logs(enabled: bool) -> None:
    await _execute(
        """
        INSERT INTO app_settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (_ACCEPT_KEY, "1" if enabled else "0"),
    )


async def logs_status_for(user_id: int, log_session: str) -> str:
    if not log_session:
        return "pending"
    row = await _fetchone(
        "SELECT file_name FROM crash_log_links WHERE user_id = ? AND log_session = ?",
        (user_id, log_session),
    )
    if row and row.get("file_name"):
        return "ready"
    return "pending"


def file_path(user_id: int, log_session: str) -> Path:
    return crash_log_root() / str(user_id) / f"{log_session}.log"


async def save_upload(
    *,
    user_id: int,
    log_session: str,
    app_version: str,
    app_build: str,
    payload: bytes,
) -> dict[str, Any]:
    body = payload[-MAX_BYTES:]
    destination = file_path(user_id, log_session)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".log.part")
    temporary.write_bytes(body)
    temporary.replace(destination)
    await _execute(
        """
        INSERT INTO crash_log_links (
            user_id, log_session, app_version, app_build, file_name, size_bytes
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, log_session) DO UPDATE SET
            app_version = excluded.app_version,
            app_build = excluded.app_build,
            file_name = excluded.file_name,
            size_bytes = excluded.size_bytes
        """,
        (user_id, log_session, app_version, app_build, destination.name, len(body)),
    )
    row = await _fetchone(
        """
        SELECT chat_session_id, logs_notified, app_version, app_build
        FROM crash_log_links WHERE user_id = ? AND log_session = ?
        """,
        (user_id, log_session),
    )
    return row or {}


async def note_crash_delivery(
    *,
    user_id: int,
    log_session: str,
    chat_session_id: int,
    crash_event_id: str,
    logs_already_ready: bool,
) -> None:
    if not log_session:
        return
    notified = 1 if logs_already_ready else 0
    await _execute(
        """
        INSERT INTO crash_log_links (
            user_id, log_session, chat_session_id, crash_event_id, logs_notified
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, log_session) DO UPDATE SET
            chat_session_id = excluded.chat_session_id,
            crash_event_id = excluded.crash_event_id,
            logs_notified = CASE
                WHEN excluded.logs_notified = 1 THEN 1
                ELSE crash_log_links.logs_notified
            END
        """,
        (user_id, log_session, chat_session_id, crash_event_id, notified),
    )


async def mark_logs_notified(user_id: int, log_session: str) -> None:
    await _execute(
        "UPDATE crash_log_links SET logs_notified = 1 WHERE user_id = ? AND log_session = ?",
        (user_id, log_session),
    )


async def link_for_admin(log_session: str) -> dict[str, Any] | None:
    return await _fetchone(
        """
        SELECT user_id, log_session, app_version, app_build, file_name, size_bytes, chat_session_id
        FROM crash_log_links WHERE log_session = ?
        ORDER BY created_at DESC
        """,
        (log_session,),
    )
