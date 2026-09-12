"""Unit tests for query job queue + SSE bridge (no Cursor)."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_db_file: str | None = None
_kb_dir: str | None = None


def setUpModule() -> None:
    global _db_file, _kb_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_API_TOKEN"] = "query-jobs-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000099"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    os.environ["KB_APP_QUERY_JOBS_ENABLED"] = "true"
    Path(_kb_dir).mkdir(parents=True, exist_ok=True)


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


class TestQueryJobService(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from config import config
        import utils.db_helpers as db_helpers

        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])
        config.KB_APP_QUERY_JOBS_ENABLED = True
        config.MAX_CONCURRENT_QUERY_JOBS = 1
        config.QUERY_JOB_EVENT_POLL_MS = 20
        db_helpers._db_instance = None  # type: ignore[attr-defined]

    def test_enqueue_claim_events_complete(self) -> None:
        async def _run() -> None:
            from utils.db_helpers import get_db
            from kb_app_api.query_jobs.service import QueryJobService

            db = await get_db()
            user = await db.ensure_user(9000000009000099, "jobs-test")
            session = await db.create_session(int(user["id"]), "empty_chat")
            service = QueryJobService()
            job = await service.enqueue(
                session_id=int(session["id"]),
                user_id=int(user["id"]),
                telegram_user_id=9000000009000099,
                query_text="hello jobs",
                use_knowledge_base=False,
            )
            claimed = await service.claim_next(max_concurrent=1)
            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(claimed.id, job.id)
            self.assertEqual(claimed.status, "running")
            self.assertIsNone(await service.claim_next(max_concurrent=1))

            seq1 = await service.append_event(job.id, "activity", "thinking")
            seq2 = await service.append_event(job.id, "delta", "Hi")
            self.assertEqual(seq1, 1)
            self.assertEqual(seq2, 2)
            events = await service.list_events_after(job.id, 0)
            self.assertEqual([e.kind for e in events], ["activity", "delta"])
            await service.complete(job.id, assistant_message_id=None)
            done = await service.get_job(job.id)
            assert done is not None
            self.assertEqual(done.status, "done")
            terminal = await service.list_events_after(job.id, 2)
            self.assertEqual(terminal[-1].kind, "done")

        asyncio.run(_run())

    def test_sse_bridge_reads_events(self) -> None:
        async def _run() -> None:
            from utils.db_helpers import get_db
            from kb_app_api.query_jobs.service import QueryJobService
            from kb_app_api.query_jobs.sse_bridge import run_job_event_bridge

            db = await get_db()
            user = await db.ensure_user(9000000009000099, "jobs-test")
            session = await db.create_session(int(user["id"]), "empty_chat")
            service = QueryJobService()
            job = await service.enqueue(
                session_id=int(session["id"]),
                user_id=int(user["id"]),
                telegram_user_id=9000000009000099,
                query_text="stream",
            )
            await service.claim_next(max_concurrent=2)

            async def producer() -> None:
                await asyncio.sleep(0.05)
                await service.append_event(job.id, "delta", "Hello")
                await service.append_event(job.id, "delta", " world")
                await service.complete(job.id, assistant_message_id=None)

            queue: asyncio.Queue = asyncio.Queue()
            err_holder: list = [None]
            prod = asyncio.create_task(producer())
            await run_job_event_bridge(
                job_id=job.id,
                queue=queue,
                err_holder=err_holder,
                jobs=service,
            )
            await prod
            items = []
            while True:
                item = await queue.get()
                if item is None:
                    break
                items.append(item)
            self.assertEqual(items, [("delta", "Hello"), ("delta", " world")])
            self.assertIsNone(err_holder[0])

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
