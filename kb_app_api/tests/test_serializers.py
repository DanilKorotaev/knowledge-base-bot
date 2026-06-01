"""Unit tests for KB App API message serializers."""
from __future__ import annotations

import unittest

from kb_app_api.serializers import attachment_to_kb, infer_content_format, message_to_kb, messages_to_kb


class TestMessageSerializers(unittest.TestCase):
    def test_infer_content_format_assistant_markdown(self) -> None:
        self.assertEqual(infer_content_format("assistant", "**bold**"), "markdown")

    def test_infer_content_format_assistant_html(self) -> None:
        self.assertEqual(infer_content_format("assistant", "Hello <b>world</b>"), "html")

    def test_infer_content_format_user_plain(self) -> None:
        self.assertEqual(infer_content_format("user", "**not md**"), "plain")

    def test_message_to_kb_with_attachment(self) -> None:
        msg = {
            "id": 42,
            "role": "user",
            "content": "voice note",
            "created_at": "2026-06-01T12:00:00",
        }
        att = {
            "id": 7,
            "file_type": "voice",
            "file_name": "voice.ogg",
            "file_size": 1234,
        }
        out = message_to_kb(1, msg, attachments=[att], transcription_by_att={7: "Привет"})
        self.assertEqual(out["id"], "42")
        self.assertEqual(out["content_format"], "plain")
        self.assertEqual(out["transcription"], "Привет")
        self.assertEqual(len(out["attachments"]), 1)
        self.assertEqual(out["attachments"][0]["download_url"], "/api/sessions/1/attachments/7/file")
        self.assertEqual(out["attachments"][0]["transcription"], "Привет")

    def test_attachment_to_kb_photo_mime(self) -> None:
        att = {"id": 3, "file_type": "photo", "file_name": "pic.jpg", "file_size": 99}
        out = attachment_to_kb(5, att, {})
        self.assertEqual(out["mime_type"], "image/jpeg")
        self.assertEqual(out["download_url"], "/api/sessions/5/attachments/3/file")

    def test_messages_to_kb_batch(self) -> None:
        msgs = [
            {"id": 1, "role": "assistant", "content": "- item", "created_at": "2026-06-01T12:00:00"},
        ]
        out = messages_to_kb(2, msgs, {1: []}, {})
        self.assertEqual(out[0]["content_format"], "markdown")


if __name__ == "__main__":
    unittest.main()
