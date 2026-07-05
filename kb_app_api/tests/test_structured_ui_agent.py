"""Tests for structured UI agent parse + resolve (no real Cursor CLI)."""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kb_app_api.structured_ui.agent import resolve_ui_event
from kb_app_api.structured_ui.mock_flow import apply_mock_ui_event
from kb_app_api.structured_ui.response_parse import (
    StructuredUIAgentParseError,
    parse_agent_ui_event_payload,
)
from kb_app_api.structured_ui.validate import validate_screen_document


def _sample_agent_json() -> str:
    doc = apply_mock_ui_event(action_id="confirm_yes", component_id="btn_yes").screen
    payload = {
        "assistant_content": "Custom agent reply.",
        "user_content": "[UI] Yes",
        "screen": doc,
    }
    return json.dumps(payload, ensure_ascii=False)


class TestStructuredUIAgentParse(unittest.TestCase):
    def test_parse_plain_json(self) -> None:
        parsed = parse_agent_ui_event_payload(_sample_agent_json())
        self.assertEqual(parsed["assistant_content"], "Custom agent reply.")
        self.assertEqual(parsed["user_content"], "[UI] Yes")
        validate_screen_document(parsed["screen"])

    def test_parse_fenced_json(self) -> None:
        raw = f"Here is the screen:\n```json\n{_sample_agent_json()}\n```"
        parsed = parse_agent_ui_event_payload(raw)
        self.assertEqual(parsed["assistant_content"], "Custom agent reply.")

    def test_parse_rejects_missing_screen(self) -> None:
        with self.assertRaises(StructuredUIAgentParseError):
            parse_agent_ui_event_payload('{"assistant_content": "x"}')


class TestResolveUIEvent(unittest.IsolatedAsyncioTestCase):
    async def test_uses_mock_when_agent_disabled(self) -> None:
        with patch("config.config.STRUCTURED_UI_AGENT_ENABLED", False):
            result = await resolve_ui_event(
                session_id=1,
                action_id="start",
                component_id="bootstrap",
                session_messages=[],
            )
        self.assertEqual(result.assistant_content, "Interactive UI ready.")

    async def test_agent_success_when_enabled(self) -> None:
        mock_cursor = AsyncMock()
        mock_cursor.run_simple_prompt = AsyncMock(return_value=_sample_agent_json())
        with (
            patch("config.config.STRUCTURED_UI_AGENT_ENABLED", True),
            patch("config.config.STRUCTURED_UI_AGENT_MOCK_FALLBACK", True),
            patch("services.cursor_cli_service.CursorCLIService", return_value=mock_cursor),
        ):
            result = await resolve_ui_event(
                session_id=1,
                action_id="confirm_yes",
                component_id="btn_yes",
                session_messages=[{"role": "user", "content": "hello"}],
            )
        self.assertEqual(result.assistant_content, "Custom agent reply.")
        mock_cursor.run_simple_prompt.assert_awaited_once()

    async def test_agent_falls_back_to_mock_on_bad_json(self) -> None:
        mock_cursor = AsyncMock()
        mock_cursor.run_simple_prompt = AsyncMock(return_value="not json at all")
        with (
            patch("config.config.STRUCTURED_UI_AGENT_ENABLED", True),
            patch("config.config.STRUCTURED_UI_AGENT_MOCK_FALLBACK", True),
            patch("services.cursor_cli_service.CursorCLIService", return_value=mock_cursor),
        ):
            result = await resolve_ui_event(
                session_id=1,
                action_id="start",
                component_id="bootstrap",
                session_messages=[],
            )
        self.assertEqual(result.assistant_content, "Interactive UI ready.")


if __name__ == "__main__":
    unittest.main()
