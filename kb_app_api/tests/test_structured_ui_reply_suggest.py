"""Unit tests for structured UI reply suggest helpers."""

from __future__ import annotations

import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import kb_app_api.structured_ui.reply_suggest as reply_suggest
from kb_app_api.client_metadata import structured_ui_allowed_from_headers
from kb_app_api.structured_ui.reply_suggest import suggest_structured_ui_for_reply


class TestStructuredUIAllowedHeader(unittest.TestCase):
    def test_true_values(self) -> None:
        self.assertTrue(structured_ui_allowed_from_headers({"X-KB-Structured-UI": "1"}))
        self.assertTrue(structured_ui_allowed_from_headers({"x-kb-structured-ui": "true"}))

    def test_false_or_missing(self) -> None:
        self.assertFalse(structured_ui_allowed_from_headers({}))
        self.assertFalse(structured_ui_allowed_from_headers({"X-KB-Structured-UI": "0"}))


class TestSuggestStructuredUIForReply(unittest.IsolatedAsyncioTestCase):
    async def test_null_screen(self) -> None:
        mock_inst = MagicMock()
        mock_inst.run_simple_prompt = AsyncMock(return_value='{"screen": null}')
        with (
            patch.object(reply_suggest.config, "STRUCTURED_UI_IN_REPLIES_ENABLED", True),
            patch("services.cursor_cli_service.CursorCLIService", return_value=mock_inst),
        ):
            result = await suggest_structured_ui_for_reply(
                assistant_reply="Вот полный ответ без выбора.",
                session_messages=[],
            )
        self.assertIsNone(result)

    async def test_valid_screen(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [
                    {"type": "text", "id": "t", "text": "Приоритет?"},
                    {
                        "type": "button",
                        "id": "b1",
                        "label": "Высокий",
                        "action_id": "prio_high",
                    },
                ],
            },
        }
        mock_inst = MagicMock()
        mock_inst.run_simple_prompt = AsyncMock(return_value=json.dumps(doc))
        with (
            patch.object(reply_suggest.config, "STRUCTURED_UI_IN_REPLIES_ENABLED", True),
            patch("services.cursor_cli_service.CursorCLIService", return_value=mock_inst),
        ):
            result = await suggest_structured_ui_for_reply(
                assistant_reply="Есть три задачи. Какую берём первой?",
                session_messages=[{"role": "user", "content": "что в приоритете"}],
            )
        self.assertEqual(result, doc)

    async def test_disabled_env(self) -> None:
        with patch.object(reply_suggest.config, "STRUCTURED_UI_IN_REPLIES_ENABLED", False):
            result = await suggest_structured_ui_for_reply(
                assistant_reply="hi",
                session_messages=[],
            )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
