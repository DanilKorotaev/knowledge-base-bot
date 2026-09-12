"""Background query jobs: durable queue + event stream for SSE proxy."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import config
from database.postgresql_db import PostgreSQLDatabase
from database.sqlite_db import SQLiteDatabase
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})


@dataclass(frozen=True)
class QueryJob:
    id: str
    session_id: int
    user_id: int
    telegram_user_id: int
    status: str
    query_text: str
    use_knowledge_base: bool
    allow_structured_ui: bool
    attached_files: list[str]
    error_message: str | None = None
    assistant_message_id: int | None = None


@dataclass(frozen=True)
class QueryJobEvent:
    seq: int
    kind: str
    payload: str


def _row_to_job(row: dict[str, Any]) -> QueryJob:
    raw_files = row.get("attached_files_json")
    files: list[str] = []
    if isinstance(raw_files, str) and raw_files.strip():
        try:
            parsed = json.loads(raw_files)
            if isinstance(parsed, list):
                files = [str(item) for item in parsed]
        except json.JSONDecodeError:
            files = []
    use_kb = row.get("use_knowledge_base")
    allow_sui = row.get("allow_structured_ui")
    return QueryJob(
        id=str(row["id"]),
        session_id=int(row["session_id"]),
        user_id=int(row["user_id"]),
        telegram_user_id=int(row["telegram_user_id"]),
        status=str(row["status"]),
        query_text=str(row["query_text"] or ""),
        use_knowledge_base=bool(use_kb) if not isinstance(use_kb, int) else bool(use_kb),
        allow_structured_ui=bool(allow_sui) if not isinstance(allow_sui, int) else bool(allow_sui),
        attached_files=files,
        error_message=row.get("error_message"),
        assistant_message_id=(
            int(row["assistant_message_id"]) if row.get("assistant_message_id") is not None else None
        ),
    )


class QueryJobService:
    """Enqueue / claim / stream events for Cursor work outside uvicorn."""

    async def enqueue(
        self,
        *,
        session_id: int,
        user_id: int,
        telegram_user_id: int,
        query_text: str,
        use_knowledge_base: bool = True,
        allow_structured_ui: bool = False,
        attached_files: list[Path] | None = None,
    ) -> QueryJob:
        job_id = str(uuid.uuid4())
        files_json = json.dumps(
            [str(path) for path in (attached_files or [])],
            ensure_ascii=False,
        )
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO query_jobs (
                        id, session_id, user_id, telegram_user_id, status, query_text,
                        use_knowledge_base, allow_structured_ui, attached_files_json
                    )
                    VALUES ($1::uuid, $2, $3, $4, 'queued', $5, $6, $7, $8)
                    RETURNING *
                    """,
                    job_id,
                    session_id,
                    user_id,
                    telegram_user_id,
                    query_text,
                    use_knowledge_base,
                    allow_structured_ui,
                    files_json,
                )
                job = _row_to_job(dict(row))
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                await conn.execute(
                    """
                    INSERT INTO query_jobs (
                        id, session_id, user_id, telegram_user_id, status, query_text,
                        use_knowledge_base, allow_structured_ui, attached_files_json
                    )
                    VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)
                    """,
                    (
                        job_id,
                        session_id,
                        user_id,
                        telegram_user_id,
                        query_text,
                        1 if use_knowledge_base else 0,
                        1 if allow_structured_ui else 0,
                        files_json,
                    ),
                )
                await conn.commit()
                cursor = await conn.execute("SELECT * FROM query_jobs WHERE id = ?", (job_id,))
                row = await cursor.fetchone()
                assert row is not None
                cols = [item[0] for item in cursor.description]
                job = _row_to_job(dict(zip(cols, row)))
        logger.info(
            "query_job enqueued job_id=%s session_id=%s telegram_user_id=%s",
            job.id,
            job.session_id,
            job.telegram_user_id,
        )
        return job

    async def get_job(self, job_id: str) -> QueryJob | None:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM query_jobs WHERE id = $1::uuid", job_id)
                return _row_to_job(dict(row)) if row else None
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            cursor = await conn.execute("SELECT * FROM query_jobs WHERE id = ?", (job_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            cols = [item[0] for item in cursor.description]
            return _row_to_job(dict(zip(cols, row)))

    async def claim_next(self, *, max_concurrent: int | None = None) -> QueryJob | None:
        limit = max_concurrent if max_concurrent is not None else config.MAX_CONCURRENT_QUERY_JOBS
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    running = await conn.fetchval(
                        "SELECT COUNT(*) FROM query_jobs WHERE status = 'running'"
                    )
                    if int(running or 0) >= limit:
                        return None
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM query_jobs
                        WHERE status = 'queued'
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                    )
                    if not row:
                        return None
                    updated = await conn.fetchrow(
                        """
                        UPDATE query_jobs
                        SET status = 'running',
                            started_at = COALESCE(started_at, NOW()),
                            heartbeat_at = NOW()
                        WHERE id = $1::uuid
                        RETURNING *
                        """,
                        row["id"],
                    )
                    return _row_to_job(dict(updated))
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM query_jobs WHERE status = 'running'"
                )
                running = (await cursor.fetchone() or (0,))[0]
                if int(running) >= limit:
                    await conn.execute("COMMIT")
                    return None
                cursor = await conn.execute(
                    """
                    SELECT * FROM query_jobs
                    WHERE status = 'queued'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """
                )
                row = await cursor.fetchone()
                if not row:
                    await conn.execute("COMMIT")
                    return None
                cols = [item[0] for item in cursor.description]
                job_id = dict(zip(cols, row))["id"]
                await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'running',
                        started_at = COALESCE(started_at, CURRENT_TIMESTAMP),
                        heartbeat_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (job_id,),
                )
                cursor = await conn.execute("SELECT * FROM query_jobs WHERE id = ?", (job_id,))
                updated = await cursor.fetchone()
                await conn.execute("COMMIT")
                assert updated is not None
                cols = [item[0] for item in cursor.description]
                return _row_to_job(dict(zip(cols, updated)))
            except Exception:
                await conn.execute("ROLLBACK")
                raise

    async def append_event(self, job_id: str, kind: str, payload: str = "") -> int:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    seq = await conn.fetchval(
                        """
                        SELECT COALESCE(MAX(seq), 0) + 1
                        FROM query_job_events
                        WHERE job_id = $1::uuid
                        """,
                        job_id,
                    )
                    await conn.execute(
                        """
                        INSERT INTO query_job_events (job_id, seq, kind, payload)
                        VALUES ($1::uuid, $2, $3, $4)
                        """,
                        job_id,
                        int(seq),
                        kind,
                        payload or "",
                    )
                    await conn.execute(
                        "UPDATE query_jobs SET heartbeat_at = NOW() WHERE id = $1::uuid",
                        job_id,
                    )
                    return int(seq)
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = await conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM query_job_events WHERE job_id = ?",
                    (job_id,),
                )
                seq = int((await cursor.fetchone() or (1,))[0])
                await conn.execute(
                    """
                    INSERT INTO query_job_events (job_id, seq, kind, payload)
                    VALUES (?, ?, ?, ?)
                    """,
                    (job_id, seq, kind, payload or ""),
                )
                await conn.execute(
                    "UPDATE query_jobs SET heartbeat_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (job_id,),
                )
                await conn.execute("COMMIT")
                return seq
            except Exception:
                await conn.execute("ROLLBACK")
                raise

    async def list_events_after(self, job_id: str, after_seq: int) -> list[QueryJobEvent]:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT seq, kind, payload
                    FROM query_job_events
                    WHERE job_id = $1::uuid AND seq > $2
                    ORDER BY seq ASC
                    """,
                    job_id,
                    after_seq,
                )
                return [
                    QueryJobEvent(seq=int(r["seq"]), kind=str(r["kind"]), payload=str(r["payload"] or ""))
                    for r in rows
                ]
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            cursor = await conn.execute(
                """
                SELECT seq, kind, payload
                FROM query_job_events
                WHERE job_id = ? AND seq > ?
                ORDER BY seq ASC
                """,
                (job_id, after_seq),
            )
            rows = await cursor.fetchall()
            return [
                QueryJobEvent(seq=int(r[0]), kind=str(r[1]), payload=str(r[2] or ""))
                for r in rows
            ]

    async def complete(self, job_id: str, *, assistant_message_id: int | None) -> None:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'done',
                        assistant_message_id = $2,
                        finished_at = NOW(),
                        heartbeat_at = NOW(),
                        error_message = NULL
                    WHERE id = $1::uuid
                    """,
                    job_id,
                    assistant_message_id,
                )
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'done',
                        assistant_message_id = ?,
                        finished_at = CURRENT_TIMESTAMP,
                        heartbeat_at = CURRENT_TIMESTAMP,
                        error_message = NULL
                    WHERE id = ?
                    """,
                    (assistant_message_id, job_id),
                )
                await conn.commit()
        await self.append_event(job_id, "done", "")

    async def fail(self, job_id: str, error_message: str) -> None:
        db = await get_db()
        message = (error_message or "query failed")[:2000]
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'failed',
                        error_message = $2,
                        finished_at = NOW(),
                        heartbeat_at = NOW()
                    WHERE id = $1::uuid
                    """,
                    job_id,
                    message,
                )
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'failed',
                        error_message = ?,
                        finished_at = CURRENT_TIMESTAMP,
                        heartbeat_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (message, job_id),
                )
                await conn.commit()
        await self.append_event(job_id, "error", message)

    async def heartbeat(self, job_id: str) -> None:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE query_jobs SET heartbeat_at = NOW() WHERE id = $1::uuid",
                    job_id,
                )
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                await conn.execute(
                    "UPDATE query_jobs SET heartbeat_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (job_id,),
                )
                await conn.commit()

    async def reclaim_stale_running(self, *, stale_after_sec: int | None = None) -> int:
        """Re-queue jobs stuck in running without heartbeat (worker crash)."""
        stale = stale_after_sec if stale_after_sec is not None else config.QUERY_JOB_STALE_RUNNING_SEC
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'queued',
                        started_at = NULL,
                        heartbeat_at = NULL,
                        error_message = 'reclaimed after stale running'
                    WHERE status = 'running'
                      AND COALESCE(heartbeat_at, started_at, created_at)
                          < NOW() - ($1::double precision * INTERVAL '1 second')
                    """,
                    float(stale),
                )
            # asyncpg returns status string like "UPDATE 2"
            try:
                return int(str(result).split()[-1])
            except (ValueError, IndexError):
                return 0
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            cursor = await conn.execute(
                """
                UPDATE query_jobs
                SET status = 'queued',
                    started_at = NULL,
                    heartbeat_at = NULL,
                    error_message = 'reclaimed after stale running'
                WHERE status = 'running'
                  AND (
                    CAST(strftime('%s', COALESCE(heartbeat_at, started_at, created_at)) AS INTEGER)
                    < CAST(strftime('%s', 'now') AS INTEGER) - ?
                  )
                """,
                (stale,),
            )
            await conn.commit()
            return cursor.rowcount or 0
