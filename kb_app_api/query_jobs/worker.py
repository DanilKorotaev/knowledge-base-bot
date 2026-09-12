"""Query worker process: claim jobs and run Cursor outside uvicorn."""
from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path

from config import config
from kb_app_api.query_jobs.service import QueryJob, QueryJobService
from services.query_processing_service import QueryProcessingService
from utils.db_helpers import close_db, get_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("kb_app_api.query_worker")

_stop = asyncio.Event()


def _request_stop(*_args: object) -> None:
    _stop.set()


async def _run_one(job: QueryJob, service: QueryJobService) -> None:
    logger.info(
        "query_job start job_id=%s session_id=%s status=running",
        job.id,
        job.session_id,
    )

    async def on_chunk(chunk: str) -> None:
        if chunk:
            await service.append_event(job.id, "delta", chunk)

    async def on_activity(label: str) -> None:
        if label:
            await service.append_event(job.id, "activity", label)

    attached = [Path(path) for path in job.attached_files if path]
    qps = QueryProcessingService()
    try:
        reply, _changes = await qps.process_query_for_api(
            job.query_text,
            job.session_id,
            job.telegram_user_id,
            use_knowledge_base=job.use_knowledge_base,
            attached_files=attached or None,
            save_user_message=False,
            on_chunk=on_chunk,
            on_activity=on_activity,
            allow_structured_ui=job.allow_structured_ui,
        )
        db = await get_db()
        messages = await db.get_session_messages(job.session_id)
        assistant_id = None
        for message in reversed(messages):
            if str(message.get("role")) == "assistant":
                assistant_id = int(message["id"])
                break
        await service.complete(job.id, assistant_message_id=assistant_id)
        logger.info(
            "query_job done job_id=%s session_id=%s assistant_message_id=%s reply_chars=%s",
            job.id,
            job.session_id,
            assistant_id,
            len(reply or ""),
        )
    except BaseException as exc:
        logger.exception("query_job failed job_id=%s", job.id)
        await service.fail(job.id, str(exc))


async def worker_loop() -> None:
    await get_db()
    service = QueryJobService()
    reclaimed = await service.reclaim_stale_running()
    if reclaimed:
        logger.warning("reclaimed %s stale running query jobs", reclaimed)

    logger.info(
        "query worker started max_concurrent=%s jobs_enabled_flag=%s",
        config.MAX_CONCURRENT_QUERY_JOBS,
        config.KB_APP_QUERY_JOBS_ENABLED,
    )
    in_flight: set[asyncio.Task[None]] = set()

    while not _stop.is_set():
        # Drop finished tasks
        done = {task for task in in_flight if task.done()}
        for task in done:
            in_flight.discard(task)
            try:
                task.result()
            except Exception:
                logger.exception("query job task crashed")

        slots = max(0, config.MAX_CONCURRENT_QUERY_JOBS - len(in_flight))
        claimed_any = False
        for _ in range(slots):
            job = await service.claim_next()
            if job is None:
                break
            claimed_any = True
            task = asyncio.create_task(_run_one(job, service), name=f"query-job-{job.id}")
            in_flight.add(task)

        try:
            await asyncio.wait_for(_stop.wait(), timeout=0.4 if claimed_any else 0.8)
        except asyncio.TimeoutError:
            pass

    if in_flight:
        logger.info("query worker shutting down; waiting for %s jobs", len(in_flight))
        await asyncio.gather(*in_flight, return_exceptions=True)
    await close_db()
    logger.info("query worker stopped")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _request_stop())
    try:
        loop.run_until_complete(worker_loop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
