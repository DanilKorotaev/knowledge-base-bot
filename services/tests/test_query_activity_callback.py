"""Throttled Telegram activity status callback."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock

from services.query_processing_service import _make_throttled_activity_callback


class TestThrottledActivityCallback(unittest.IsolatedAsyncioTestCase):
    async def test_edits_status_with_label(self) -> None:
        edit = AsyncMock()
        on_activity = _make_throttled_activity_callback(
            edit_status=edit,
            throttle_sec=0,
            session_suffix=" · #1",
        )
        await on_activity("Запускаю тесты…")
        edit.assert_awaited_once_with("⏳ Запускаю тесты… · #1")

    async def test_throttles_rapid_updates(self) -> None:
        edit = AsyncMock()
        on_activity = _make_throttled_activity_callback(
            edit_status=edit,
            throttle_sec=60,
            session_suffix="",
        )
        await on_activity("first")
        await on_activity("second")
        edit.assert_awaited_once_with("⏳ first")

    async def test_ignores_empty_label(self) -> None:
        edit = AsyncMock()
        on_activity = _make_throttled_activity_callback(
            edit_status=edit,
            throttle_sec=0,
        )
        await on_activity("   ")
        edit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
