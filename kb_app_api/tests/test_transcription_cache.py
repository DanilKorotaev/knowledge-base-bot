"""Tests for idempotent transcription cache."""
from __future__ import annotations

import asyncio
import unittest

from kb_app_api.transcription_cache import TranscriptionCache, validate_client_transcription_id


class TestTranscriptionCache(unittest.IsolatedAsyncioTestCase):
    async def test_ready_hit_skips_second_factory(self) -> None:
        cache = TranscriptionCache(ttl_sec=60)
        runs = {"n": 0}

        async def factory() -> str:
            runs["n"] += 1
            await asyncio.sleep(0.01)
            return "hello"

        a = await cache.get_or_run(1, "cap-1", factory)
        b = await cache.get_or_run(1, "cap-1", factory)
        self.assertEqual(a, "hello")
        self.assertEqual(b, "hello")
        self.assertEqual(runs["n"], 1)
        self.assertEqual(cache.stats_for(1, "cap-1")["whisper_runs"], 1)

    async def test_coalesce_inflight(self) -> None:
        cache = TranscriptionCache(ttl_sec=60)
        runs = {"n": 0}
        started = asyncio.Event()

        async def factory() -> str:
            runs["n"] += 1
            started.set()
            await asyncio.sleep(0.05)
            return "joined"

        t1 = asyncio.create_task(cache.get_or_run(7, "same", factory))
        await started.wait()
        t2 = asyncio.create_task(cache.get_or_run(7, "same", factory))
        a, b = await asyncio.gather(t1, t2)
        self.assertEqual(a, "joined")
        self.assertEqual(b, "joined")
        self.assertEqual(runs["n"], 1)

    async def test_failed_allows_retry(self) -> None:
        cache = TranscriptionCache(ttl_sec=60)
        runs = {"n": 0}

        async def factory() -> str:
            runs["n"] += 1
            if runs["n"] == 1:
                raise RuntimeError("boom")
            return "recovered"

        with self.assertRaises(RuntimeError):
            await cache.get_or_run(1, "x", factory)
        text = await cache.get_or_run(1, "x", factory)
        self.assertEqual(text, "recovered")
        self.assertEqual(runs["n"], 2)

    def test_validate_id(self) -> None:
        self.assertEqual(validate_client_transcription_id("A1B2"), "A1B2")
        self.assertIsNone(validate_client_transcription_id(""))
        with self.assertRaises(ValueError):
            validate_client_transcription_id("../x")


if __name__ == "__main__":
    unittest.main()
