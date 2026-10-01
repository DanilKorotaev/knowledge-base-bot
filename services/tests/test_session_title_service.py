"""Unit tests for SessionTitleService helpers and archive session API."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from services.session_title_service import (
    SessionTitleService,
    fallback_title_from_query,
    is_unset_display_title,
)


class TestSessionTitleHelpers(unittest.TestCase):
    def test_unset_placeholders(self) -> None:
        self.assertTrue(is_unset_display_title(None))
        self.assertTrue(is_unset_display_title(""))
        self.assertTrue(is_unset_display_title("Новый чат"))
        self.assertTrue(is_unset_display_title("Session 12", 12))
        self.assertFalse(is_unset_display_title("HealthKit sync"))

    def test_fallback_truncates(self) -> None:
        long = "слово " * 40
        title = fallback_title_from_query(long, max_len=40)
        self.assertLessEqual(len(title), 41)
        self.assertTrue(title.endswith("…"))


class TestSessionTitleService(unittest.IsolatedAsyncioTestCase):
    async def test_skips_when_title_set(self) -> None:
        db = MagicMock()
        db.get_session = AsyncMock(return_value={"id": 1, "display_title": "Manual"})
        db.update_session = AsyncMock()
        cursor = MagicMock()
        cursor.run_simple_prompt = AsyncMock(return_value="Should not run")
        svc = SessionTitleService(cursor_service=cursor)
        result = await svc.maybe_set_title_after_first_reply(db, 1, user_query="hi")
        self.assertIsNone(result)
        cursor.run_simple_prompt.assert_not_called()
        db.update_session.assert_not_called()

    async def test_sets_title_from_llm(self) -> None:
        db = MagicMock()
        db.get_session = AsyncMock(return_value={"id": 5, "display_title": None})
        db.update_session = AsyncMock()
        cursor = MagicMock()
        cursor.run_simple_prompt = AsyncMock(return_value="HealthKit синхронизация")
        svc = SessionTitleService(cursor_service=cursor)
        result = await svc.maybe_set_title_after_first_reply(
            db, 5, user_query="как устроен sync?", assistant_reply="вручную"
        )
        self.assertEqual(result, "HealthKit синхронизация")
        db.update_session.assert_awaited_once_with(5, display_title="HealthKit синхронизация")


if __name__ == "__main__":
    unittest.main()
