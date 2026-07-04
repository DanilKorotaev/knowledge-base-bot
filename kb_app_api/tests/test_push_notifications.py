"""Unit-тесты APNs payload и регистрации устройств."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_db_file: str | None = None


def setUpModule() -> None:
    global _db_file
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_API_TOKEN"] = "push-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000001"
    os.environ["ACCESS_MODE"] = "open"


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


class TestApnsPayload(unittest.TestCase):
    def test_preview_plain_text_truncates(self) -> None:
        from kb_app_api.apns_push_service import preview_plain_text

        long = "a" * 200
        out = preview_plain_text(long, limit=100)
        self.assertLessEqual(len(out), 100)
        self.assertTrue(out.endswith("…"))

    def test_strip_markdown_removes_emphasis(self) -> None:
        from kb_app_api.apns_push_service import strip_markdown_for_push

        self.assertEqual(strip_markdown_for_push("**bold** and _italic_"), "bold and italic")

    def test_strip_markdown_removes_code_markers(self) -> None:
        from kb_app_api.apns_push_service import strip_markdown_for_push

        self.assertEqual(strip_markdown_for_push("Use `foo()` here"), "Use foo() here")
        self.assertEqual(
            strip_markdown_for_push("```python\nprint('hi')\n```"),
            "print('hi')",
        )

    def test_strip_markdown_link_uses_label(self) -> None:
        from kb_app_api.apns_push_service import strip_markdown_for_push

        self.assertEqual(
            strip_markdown_for_push("See [docs](https://example.com/docs)"),
            "See docs",
        )

    def test_strip_markdown_normalizes_lists_and_blockquotes(self) -> None:
        from kb_app_api.apns_push_service import strip_markdown_for_push

        self.assertEqual(
            strip_markdown_for_push("- first\n* second\n1. third\n> quote"),
            "first second third quote",
        )

    def test_strip_markdown_strips_html(self) -> None:
        from kb_app_api.apns_push_service import strip_markdown_for_push

        self.assertEqual(
            strip_markdown_for_push("<p>**Hi**</p>"),
            "Hi",
        )

    def test_preview_plain_text_avoids_markdown_artifacts(self) -> None:
        from kb_app_api.apns_push_service import preview_plain_text

        out = preview_plain_text("**Done:** updated `file.md` — see [link](https://x.test/a)")
        self.assertNotIn("**", out)
        self.assertNotIn("`", out)
        self.assertIn("Done:", out)
        self.assertIn("file.md", out)
        self.assertIn("link", out)
        self.assertNotIn("https://x.test/a", out)

    def test_preview_plain_text_multiline_collapses(self) -> None:
        from kb_app_api.apns_push_service import preview_plain_text

        out = preview_plain_text("Line one\n\nLine two")
        self.assertEqual(out, "Line one Line two")

    def test_build_chat_reply_payload(self) -> None:
        from kb_app_api.apns_push_service import build_chat_reply_payload

        payload = build_chat_reply_payload(
            session_id=42,
            message_id=99,
            title="My chat",
            body_preview="Hello world",
        )
        self.assertEqual(payload["session_id"], "42")
        self.assertEqual(payload["message_id"], "99")
        self.assertEqual(payload["type"], "chat_reply_ready")
        self.assertEqual(payload["aps"]["alert"]["title"], "My chat")
        self.assertEqual(payload["aps"]["thread-id"], "42")


@unittest.skipUnless(TestClient is not None, "Нужен fastapi")
class TestDevicesRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer push-test-bearer"}

    def test_register_and_unregister_device(self) -> None:
        body = {
            "device_token": "abc123deadbeef",
            "platform": "ios",
            "apns_environment": "sandbox",
            "app_version": "0.1.0",
        }
        r = self.client.post("/api/devices", json=body, headers=self.headers)
        self.assertEqual(r.status_code, 204)

        r2 = self.client.delete("/api/devices/abc123deadbeef", headers=self.headers)
        self.assertEqual(r2.status_code, 204)

    def test_register_requires_bearer(self) -> None:
        r = self.client.post(
            "/api/devices",
            json={"device_token": "x", "platform": "ios", "apns_environment": "sandbox"},
        )
        self.assertEqual(r.status_code, 401)


class TestPushDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_notify_skips_without_devices(self) -> None:
        from kb_app_api.push_dispatch import notify_chat_reply_ready

        with patch("kb_app_api.push_dispatch.send_chat_reply_to_devices", new_callable=AsyncMock) as send_mock:
            await notify_chat_reply_ready(session_id=999999, message_id=1, reply_text="hi")
            send_mock.assert_not_called()
