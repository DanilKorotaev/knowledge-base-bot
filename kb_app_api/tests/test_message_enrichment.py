"""Unit tests for changed files enrichment in chat messages."""
from __future__ import annotations

import unittest

from kb_app_api.message_enrichment import _related_changed_files_by_message


class TestMessageEnrichment(unittest.TestCase):
    def test_related_changed_files_by_message_maps_changes_to_reply_window(self) -> None:
        messages = [
            {"id": 1, "role": "user", "created_at": "2026-06-01T12:00:00Z"},
            {"id": 2, "role": "assistant", "created_at": "2026-06-01T12:00:10Z"},
            {"id": 3, "role": "user", "created_at": "2026-06-01T12:00:20Z"},
            {"id": 4, "role": "assistant", "created_at": "2026-06-01T12:00:30Z"},
        ]
        changes = [
            {"id": 10, "file_path": "a.md", "created_at": "2026-06-01T12:00:05Z"},
            {"id": 11, "file_path": "b.md", "created_at": "2026-06-01T12:00:12Z"},
            {"id": 12, "file_path": "c.md", "created_at": "2026-06-01T12:00:25Z"},
        ]

        per_message, source = _related_changed_files_by_message(messages, changes)

        self.assertEqual([item["id"] for item in per_message[2]], [10])
        self.assertEqual([item["id"] for item in per_message[4]], [12, 11])
        self.assertEqual(source[2], "reply")
        self.assertEqual(source[4], "reply")

    def test_related_changed_files_falls_back_to_recent_for_latest_assistant(self) -> None:
        messages = [
            {"id": 1, "role": "assistant", "created_at": "2026-06-01T12:00:10Z"},
        ]
        changes = [
            {"id": 20, "file_path": "z.md", "created_at": "2026-06-01T12:00:20Z"},
        ]

        per_message, source = _related_changed_files_by_message(messages, changes)

        self.assertEqual([item["id"] for item in per_message[1]], [20])
        self.assertEqual(source[1], "recent")


if __name__ == "__main__":
    unittest.main()
