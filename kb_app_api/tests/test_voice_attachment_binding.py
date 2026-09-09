"""Voice/photo must bind to their own message_id before Cursor runs (no last-user race)."""
from __future__ import annotations

import sys
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


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestVoiceAttachmentBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer smoke-test-bearer"}

    def _create_session(self) -> str:
        response = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Voice bind"},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["session"]["id"]

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_voice_attaches_before_pipeline_and_keeps_own_message(self, mock_process: AsyncMock) -> None:
        """
        Regression for session 241: voice finished after a later photo compose and
        `attach_voice_to_last_user_message` stole the clip onto the photo message.
        """
        sid = self._create_session()
        stolen_onto: dict[str, int] = {}

        async def process_and_inject_newer_user(*_args, **kwargs):
            # Simulate a concurrent compose creating a newer user message while Cursor runs.
            from utils.db_helpers import get_db

            db = await get_db()
            newer = await db.add_message(int(sid), "user", "photo-only compose")
            stolen_onto["newer_id"] = int(newer["id"])
            return ("ok", [])

        mock_process.side_effect = process_and_inject_newer_user

        response = self.client.post(
            f"/api/sessions/{sid}/messages/voice",
            headers=self.headers,
            data={"content": "Как-будто у нас что-то пошло не так."},
            files=[("audio", ("note.m4a", b"\x00\x01\x02", "audio/mp4"))],
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        users = [m for m in body["messages"] if m["role"] == "user"]
        self.assertGreaterEqual(len(users), 2)

        voice_msg = next(m for m in users if m["content"].startswith("Как-будто"))
        photo_msg = next(m for m in users if m["id"] == stolen_onto["newer_id"])

        voice_types = [a["file_type"] for a in voice_msg.get("attachments", [])]
        self.assertIn("voice", voice_types)
        self.assertFalse(any(a.get("file_type") == "voice" for a in photo_msg.get("attachments", [])))

        mock_process.assert_awaited_once()
        self.assertFalse(mock_process.await_args.kwargs["save_user_message"])

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_attachment_endpoint_binds_before_pipeline(self, mock_process: AsyncMock) -> None:
        mock_process.return_value = ("ok", [])
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/attachments",
            headers=self.headers,
            data={"message": "look"},
            files=[("file", ("shot.jpg", b"fake-jpg", "image/jpeg"))],
        )
        self.assertEqual(response.status_code, 201)
        user = next(m for m in response.json()["messages"] if m["role"] == "user")
        self.assertEqual(user["content"], "look")
        self.assertEqual(len(user["attachments"]), 1)
        self.assertEqual(user["attachments"][0]["file_type"], "photo")
        self.assertFalse(mock_process.await_args.kwargs["save_user_message"])


if __name__ == "__main__":
    unittest.main()
