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
    created_at: str | None = None
    started_at: str | None = None


@dataclass(frozen=True)
class QueryJobEvent:
    seq: int
    kind: str
    payload: str


def _fmt_ts(raw: Any) -> str | None:
    if raw is None:
        return None
    if hasattr(raw, "isoformat"):
        try:
            return raw.isoformat().replace("+00:00", "Z")  # type: ignore[no-any-return]
        except Exception:
            pass
    text = str(raw).strip()
    return text or None


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
        created_at=_fmt_ts(row.get("created_at")),
        started_at=_fmt_ts(row.get("started_at")),
    )


_SCHEMA_READY = False


async def ensure_query_jobs_schema() -> None:
    """Idempotent DDL for hosts that started before query_jobs landed in init_db."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    db = await get_db()
    if isinstance(db, PostgreSQLDatabase):
        assert db.pool is not None
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_jobs (
                    id UUID PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    telegram_user_id BIGINT NOT NULL,
                    status TEXT NOT NULL,
                    query_text TEXT NOT NULL DEFAULT '',
                    use_knowledge_base BOOLEAN NOT NULL DEFAULT TRUE,
                    allow_structured_ui BOOLEAN NOT NULL DEFAULT FALSE,
                    attached_files_json TEXT,
                    error_message TEXT,
                    assistant_message_id INTEGER,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ,
                    heartbeat_at TIMESTAMPTZ
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_jobs_status_created
                ON query_jobs(status, created_at)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_job_events (
                    job_id UUID NOT NULL REFERENCES query_jobs(id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (job_id, seq)
                )
                """
            )
    else:
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_jobs (
                    id TEXT PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    telegram_user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    query_text TEXT NOT NULL DEFAULT '',
                    use_knowledge_base INTEGER NOT NULL DEFAULT 1,
                    allow_structured_ui INTEGER NOT NULL DEFAULT 0,
                    attached_files_json TEXT,
                    error_message TEXT,
                    assistant_message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    heartbeat_at TIMESTAMP
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_jobs_status_created
                ON query_jobs(status, created_at)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_job_events (
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (job_id, seq)
                )
                """
            )
            await conn.commit()
    _SCHEMA_READY = True


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
        await ensure_query_jobs_schema()
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
        await ensure_query_jobs_schema()
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

    async def list_active(
        self,
        *,
        user_id: int | None = None,
        limit: int = 50,
    ) -> list[QueryJob]:
        """Return queued + running jobs (newest first)."""
        await ensure_query_jobs_schema()
        capped = max(1, min(int(limit or 50), 200))
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                if user_id is None:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM query_jobs
                        WHERE status IN ('queued', 'running')
                        ORDER BY created_at DESC
                        LIMIT $1
                        """,
                        capped,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM query_jobs
                        WHERE status IN ('queued', 'running') AND user_id = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                        """,
                        user_id,
                        capped,
                    )
                return [_row_to_job(dict(r)) for r in rows]
        assert isinstance(db, SQLiteDatabase)
        async with __import__("aiosqlite").connect(db.db_path) as conn:
            if user_id is None:
                cursor = await conn.execute(
                    """
                    SELECT * FROM query_jobs
                    WHERE status IN ('queued', 'running')
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (capped,),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM query_jobs
                    WHERE status IN ('queued', 'running') AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, capped),
                )
            rows = await cursor.fetchall()
            cols = [item[0] for item in cursor.description]
            return [_row_to_job(dict(zip(cols, row))) for row in rows]

    async def cancel(self, job_id: str, *, user_id: int | None = None) -> QueryJob | None:
        """Mark queued/running job cancelled. Returns updated job or None."""
        await ensure_query_jobs_schema()
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                if user_id is None:
                    row = await conn.fetchrow(
                        """
                        UPDATE query_jobs
                        SET status = 'cancelled',
                            finished_at = NOW(),
                            heartbeat_at = NOW()
                        WHERE id = $1::uuid AND status IN ('queued', 'running')
                        RETURNING *
                        """,
                        job_id,
                    )
                else:
                    row = await conn.fetchrow(
                        """
                        UPDATE query_jobs
                        SET status = 'cancelled',
                            finished_at = NOW(),
                            heartbeat_at = NOW()
                        WHERE id = $1::uuid
                          AND user_id = $2
                          AND status IN ('queued', 'running')
                        RETURNING *
                        """,
                        job_id,
                        user_id,
                    )
                if not row:
                    return None
                job = _row_to_job(dict(row))
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                if user_id is None:
                    cursor = await conn.execute(
                        """
                        UPDATE query_jobs
                        SET status = 'cancelled',
                            finished_at = CURRENT_TIMESTAMP,
                            heartbeat_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND status IN ('queued', 'running')
                        """,
                        (job_id,),
                    )
                else:
                    cursor = await conn.execute(
                        """
                        UPDATE query_jobs
                        SET status = 'cancelled',
                            finished_at = CURRENT_TIMESTAMP,
                            heartbeat_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND user_id = ? AND status IN ('queued', 'running')
                        """,
                        (job_id, user_id),
                    )
                updated = int(cursor.rowcount or 0)
                await conn.commit()
                if updated <= 0:
                    return None
                cursor = await conn.execute("SELECT * FROM query_jobs WHERE id = ?", (job_id,))
                row = await cursor.fetchone()
                if not row:
                    return None
                cols = [item[0] for item in cursor.description]
                job = _row_to_job(dict(zip(cols, row)))
        await self.append_event(job_id, "cancelled", "")
        return job

    async def claim_next(self, *, max_concurrent: int | None = None) -> QueryJob | None:
        await ensure_query_jobs_schema()
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
        updated = False
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'done',
                        assistant_message_id = $2,
                        finished_at = NOW(),
                        heartbeat_at = NOW(),
                        error_message = NULL
                    WHERE id = $1::uuid AND status = 'running'
                    """,
                    job_id,
                    assistant_message_id,
                )
                try:
                    updated = int(str(result).split()[-1]) > 0
                except (ValueError, IndexError):
                    updated = True
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                cursor = await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'done',
                        assistant_message_id = ?,
                        finished_at = CURRENT_TIMESTAMP,
                        heartbeat_at = CURRENT_TIMESTAMP,
                        error_message = NULL
                    WHERE id = ? AND status = 'running'
                    """,
                    (assistant_message_id, job_id),
                )
                await conn.commit()
                updated = bool(cursor.rowcount)
        if updated:
            await self.append_event(job_id, "done", "")

    async def fail(self, job_id: str, error_message: str) -> None:
        db = await get_db()
        message = (error_message or "query failed")[:2000]
        updated = False
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'failed',
                        error_message = $2,
                        finished_at = NOW(),
                        heartbeat_at = NOW()
                    WHERE id = $1::uuid AND status = 'running'
                    """,
                    job_id,
                    message,
                )
                try:
                    updated = int(str(result).split()[-1]) > 0
                except (ValueError, IndexError):
                    updated = True
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                cursor = await conn.execute(
                    """
                    UPDATE query_jobs
                    SET status = 'failed',
                        error_message = ?,
                        finished_at = CURRENT_TIMESTAMP,
                        heartbeat_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'running'
                    """,
                    (message, job_id),
                )
                await conn.commit()
                updated = bool(cursor.rowcount)
        if updated:
            await self.append_event(job_id, "error", message)

    async def heartbeat(self, job_id: str) -> None:
        db = await get_db()
        if isinstance(db, PostgreSQLDatabase):
            assert db.pool is not None
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs SET heartbeat_at = NOW()
                    WHERE id = $1::uuid AND status = 'running'
                    """,
                    job_id,
                )
        else:
            assert isinstance(db, SQLiteDatabase)
            async with __import__("aiosqlite").connect(db.db_path) as conn:
                await conn.execute(
                    """
                    UPDATE query_jobs SET heartbeat_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'running'
                    """,
                    (job_id,),
                )
                await conn.commit()

    async def reclaim_stale_running(self, *, stale_after_sec: int | None = None) -> int:
        """Re-queue jobs stuck in running without heartbeat (worker crash)."""
        await ensure_query_jobs_schema()
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
