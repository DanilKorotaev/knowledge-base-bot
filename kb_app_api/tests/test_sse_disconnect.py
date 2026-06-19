"""SSE stream must keep processing after the HTTP client disconnects."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kb_app_api.routes.messages import SSEQueueItem, _stream_assistant_sse  # noqa: E402


class TestSSEDisconnect(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_continues_when_client_disconnects(self) -> None:
        queue: asyncio.Queue[SSEQueueItem] = asyncio.Queue()
        err_holder: list[BaseException | None] = [None]
        pipeline_finished = asyncio.Event()

        async def run_pipeline() -> None:
            try:
                await asyncio.sleep(0.05)
            finally:
                pipeline_finished.set()
                await queue.put(None)

        await queue.put(("delta", "chunk"))

        stream = _stream_assistant_sse(
            session_id=42,
            queue=queue,
            err_holder=err_holder,
            run_pipeline=run_pipeline,
        )

        first = await anext(stream)
        self.assertIn("processing", first)

        delta = await anext(stream)
        self.assertIn("delta", delta)

        await stream.aclose()

        await asyncio.wait_for(pipeline_finished.wait(), timeout=1.0)

    async def test_stream_emits_activity_before_delta(self) -> None:
        queue: asyncio.Queue[SSEQueueItem] = asyncio.Queue()
        err_holder: list[BaseException | None] = [None]

        async def run_pipeline() -> None:
            await queue.put(None)

        await queue.put(("activity", "Запускаю тесты…"))
        await queue.put(("delta", "Hi"))

        stream = _stream_assistant_sse(
            session_id=7,
            queue=queue,
            err_holder=err_holder,
            run_pipeline=run_pipeline,
        )

        first = await anext(stream)
        self.assertIn("processing", first)

        activity = await anext(stream)
        self.assertIn("activity", activity)
        self.assertIn("Запускаю тесты", activity)

        delta = await anext(stream)
        self.assertIn("delta", delta)
        self.assertIn("Hi", delta)

        done = await anext(stream)
        self.assertIn("done", done)

        await stream.aclose()


if __name__ == "__main__":
    unittest.main()
