"""Tests for agent / channel prompt loading."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ChannelPromptLoadTests(unittest.TestCase):
    def test_load_channel_prompts_from_agent_dir(self) -> None:
        from services.cursor_cli_service import CursorCLIService

        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            with patch.dict(os.environ, {"LOCAL_KB_PATH": str(kb)}, clear=False):
                service = object.__new__(CursorCLIService)
                service.kb_path = kb

                telegram = service._load_channel_prompt("telegram")
                app = service._load_channel_prompt("app")

        self.assertIn("Telegram", telegram)
        self.assertNotIn("Structured UI", telegram)
        self.assertIn("iOS", app)
        self.assertIn("Interactive UI", app)

    def test_wrap_query_prefixes_channel(self) -> None:
        from services.cursor_cli_service import CursorCLIService

        service = object.__new__(CursorCLIService)
        service.kb_path = Path("/tmp")
        wrapped = service._wrap_query_with_channel("hello vault", "telegram")
        self.assertTrue(wrapped.startswith("# Client channel: Telegram"))
        self.assertIn("hello vault", wrapped)

    def test_channel_prefix_only_without_resume(self) -> None:
        """Documented contract: wrap helper used only when cursor_chat_id is absent."""
        from services.cursor_cli_service import CursorCLIService

        service = object.__new__(CursorCLIService)
        service.kb_path = Path("/tmp")
        # Simulate the branch in process_query: resume → no wrap
        cursor_chat_id = "chat-123"
        query = "follow-up"
        if not cursor_chat_id:
            query = service._wrap_query_with_channel(query, "app")
        self.assertEqual(query, "follow-up")

        cursor_chat_id = None
        query = "first"
        if not cursor_chat_id:
            query = service._wrap_query_with_channel(query, "app")
        self.assertIn("iOS", query)
        self.assertIn("first", query)

    def test_bot_runtime_prompt_has_no_personal_vault_paths(self) -> None:
        from services.cursor_cli_service import CursorCLIService

        service = object.__new__(CursorCLIService)
        service.kb_path = Path("/tmp")
        text = service._load_bot_prompt()
        self.assertIn("knowledge base vault", text.lower())
        self.assertNotIn("Документация/Системный промпт", text)
        self.assertNotIn("Документация/Задачи", text)
        self.assertNotIn("kb-automation", text)


if __name__ == "__main__":
    unittest.main()
