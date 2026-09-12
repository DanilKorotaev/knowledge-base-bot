"""SSE bridge: poll query_job_events and feed the existing SSE queue."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from config import config
from kb_app_api.query_jobs.service import TERMINAL_STATUSES, QueryJobService

logger = logging.getLogger(__name__)

SSEQueueItem = tuple[str, str] | None


async def run_job_event_bridge(
    *,
    job_id: str,
    queue: asyncio.Queue[SSEQueueItem],
    err_holder: list[BaseException | None],
    jobs: QueryJobService | None = None,
) -> None:
    """
    Read job events until terminal status and push onto the SSE queue.
    Does not run Cursor — that belongs to the query worker process.
    """
    service = jobs or QueryJobService()
    after_seq = 0
    poll_sec = max(0.02, config.QUERY_JOB_EVENT_POLL_MS / 1000.0)
    try:
        while True:
            events = await service.list_events_after(job_id, after_seq)
            for event in events:
                after_seq = event.seq
                if event.kind == "delta" and event.payload:
                    await queue.put(("delta", event.payload))
                elif event.kind == "activity" and event.payload:
                    await queue.put(("activity", event.payload))
                elif event.kind == "error" and event.payload:
                    err_holder[0] = RuntimeError(event.payload)
                elif event.kind == "done":
                    return
            job = await service.get_job(job_id)
            if job is None:
                err_holder[0] = RuntimeError("query job disappeared")
                return
            if job.status in TERMINAL_STATUSES:
                if job.status == "failed" and err_holder[0] is None:
                    err_holder[0] = RuntimeError(job.error_message or "query failed")
                return
            await asyncio.sleep(poll_sec)
    except BaseException as exc:
        err_holder[0] = exc
        logger.exception("query job SSE bridge failed job_id=%s", job_id)
    finally:
        await queue.put(None)


async def enqueue_and_bridge_pipeline(
    *,
    session_id: int,
    user_id: int,
    telegram_user_id: int,
    query_text: str,
    use_kb: bool,
    attached_files: list[Path] | None,
    allow_structured_ui: bool,
    queue: asyncio.Queue[SSEQueueItem],
    err_holder: list[BaseException | None],
    skip_pipeline: bool = False,
) -> str | None:
    """Enqueue a job (unless skip) and bridge its events into ``queue``."""
    if skip_pipeline:
        await queue.put(None)
        return None
    service = QueryJobService()
    job = await service.enqueue(
        session_id=session_id,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        query_text=query_text,
        use_knowledge_base=use_kb,
        allow_structured_ui=allow_structured_ui,
        attached_files=attached_files,
    )
    await run_job_event_bridge(job_id=job.id, queue=queue, err_holder=err_holder, jobs=service)
    return job.id


async def run_query_inline_or_job(
    *,
    session_id: int,
    user_id: int,
    telegram_user_id: int,
    query_text: str,
    use_kb: bool,
    attached_files: list[Path] | None,
    allow_structured_ui: bool,
    on_chunk: Callable[[str], Awaitable[None]] | None,
    on_activity: Callable[[str], Awaitable[None]] | None,
    skip_pipeline: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Non-SSE path: either enqueue+wait via events (jobs enabled) or call QPS inline.
    Returns (reply_text, changes) for callers that need it; when jobs enabled reply may be empty
    (assistant already persisted by worker).
    """
    from services.query_processing_service import QueryProcessingService

    if skip_pipeline:
        return "", []

    if not config.KB_APP_QUERY_JOBS_ENABLED:
        qps = QueryProcessingService()
        return await qps.process_query_for_api(
            query_text,
            session_id,
            telegram_user_id,
            use_knowledge_base=use_kb,
            attached_files=attached_files or None,
            save_user_message=False,
            on_chunk=on_chunk,
            on_activity=on_activity,
            allow_structured_ui=allow_structured_ui,
        )

    service = QueryJobService()
    job = await service.enqueue(
        session_id=session_id,
        user_id=user_id,
        telegram_user_id=telegram_user_id,
        query_text=query_text,
        use_knowledge_base=use_kb,
        allow_structured_ui=allow_structured_ui,
        attached_files=attached_files,
    )
    poll_sec = max(0.05, config.QUERY_JOB_EVENT_POLL_MS / 1000.0)
    after_seq = 0
    while True:
        events = await service.list_events_after(job.id, after_seq)
        for event in events:
            after_seq = event.seq
            if event.kind == "delta" and event.payload and on_chunk is not None:
                await on_chunk(event.payload)
            elif event.kind == "activity" and event.payload and on_activity is not None:
                await on_activity(event.payload)
            elif event.kind == "error" and event.payload:
                raise RuntimeError(event.payload)
        current = await service.get_job(job.id)
        if current is None:
            raise RuntimeError("query job disappeared")
        if current.status == "done":
            return "", []
        if current.status == "failed":
            raise RuntimeError(current.error_message or "query failed")
        if current.status == "cancelled":
            raise RuntimeError("query cancelled")
        await asyncio.sleep(poll_sec)
