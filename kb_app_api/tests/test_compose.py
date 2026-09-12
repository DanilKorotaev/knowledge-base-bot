"""Tests for POST /api/sessions/{id}/messages/compose."""
from __future__ import annotations

import json
import os
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

from kb_app_api.tests import test_smoke as smoke  # noqa: E402


def setUpModule() -> None:
    smoke.setUpModule()
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"


def tearDownModule() -> None:
    smoke.tearDownModule()


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestComposeMessage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from config import config

        config.KB_APP_API_TOKEN = os.environ["KB_APP_API_TOKEN"]
        config.KB_APP_API_TELEGRAM_ID = int(os.environ["KB_APP_API_TELEGRAM_ID"])
        config.ACCESS_MODE = "open"
        config.KB_APP_API_BYPASS_ACCESS_CHECK = True
        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])

        import utils.db_helpers as db_helpers

        db_helpers._db_instance = None  # type: ignore[attr-defined]

        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer smoke-test-bearer"}

    def _create_session(self) -> str:
        response = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Compose"},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["session"]["id"]

    def test_compose_requires_bearer(self) -> None:
        response = self.client.post(
            "/api/sessions/1/messages/compose",
            data={"content": "hello"},
        )
        self.assertEqual(response.status_code, 401)

    def test_compose_rejects_empty_payload(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "   "},
        )
        self.assertEqual(response.status_code, 400)

    def test_compose_rejects_empty_file(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "see file"},
            files=[("files", ("empty.bin", b"", "application/octet-stream"))],
        )
        self.assertEqual(response.status_code, 400)

    def test_compose_rejects_transcription_count_mismatch(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={
                "content": "voice",
                "audio_transcriptions": json.dumps(["one"]),
            },
            files=[
                ("audio", ("a.m4a", b"\x00\x01", "audio/mp4")),
                ("audio", ("b.m4a", b"\x00\x02", "audio/mp4")),
            ],
        )
        self.assertEqual(response.status_code, 400)

    def test_compose_rejects_too_many_files(self) -> None:
        sid = self._create_session()
        files = [
            ("files", (f"file{i}.txt", b"x", "text/plain"))
            for i in range(11)
        ]
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "too many"},
            files=files,
        )
        self.assertEqual(response.status_code, 400)

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_compose_accepts_text_and_files(self, mock_process: AsyncMock) -> None:
        mock_process.return_value = ("ok", [])
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "analyze these"},
            files=[
                ("files", ("one.jpg", b"fake-image-1", "image/jpeg")),
                ("files", ("two.jpg", b"fake-image-2", "image/jpeg")),
            ],
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        user = next(message for message in body["messages"] if message["role"] == "user")
        self.assertEqual(user["content"], "analyze these")
        self.assertEqual(len(user["attachments"]), 2)
        mock_process.assert_awaited_once()
        kwargs = mock_process.await_args.kwargs
        self.assertFalse(kwargs["save_user_message"])
        self.assertEqual(len(kwargs["attached_files"]), 2)

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_compose_accepts_voice_with_transcriptions(self, mock_process: AsyncMock) -> None:
        mock_process.return_value = ("ok", [])
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={
                "content": "note",
                "audio_transcriptions": json.dumps(["first clip", "second clip"]),
            },
            files=[
                ("audio", ("a.m4a", b"\x00\x01", "audio/mp4")),
                ("audio", ("b.m4a", b"\x00\x02", "audio/mp4")),
            ],
        )
        self.assertEqual(response.status_code, 201)
        user = next(message for message in response.json()["messages"] if message["role"] == "user")
        voice_attachments = [item for item in user["attachments"] if item["file_type"] == "voice"]
        self.assertEqual(len(voice_attachments), 2)
        mock_process.assert_awaited_once()


    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_compose_classifies_jpeg_without_image_extension_as_photo(self, mock_process: AsyncMock) -> None:
        mock_process.return_value = ("ok", [])
        sid = self._create_session()
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 32
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "screenshot"},
            files=[
                (
                    "files",
                    (
                        "Снимок_экрана_2026_09_07_в_9.21.57_PM",
                        jpeg,
                        "application/octet-stream",
                    ),
                ),
            ],
        )
        self.assertEqual(response.status_code, 201)
        user = next(message for message in response.json()["messages"] if message["role"] == "user")
        self.assertEqual(len(user["attachments"]), 1)
        self.assertEqual(user["attachments"][0]["file_type"], "photo")

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_compose_client_message_id_ack_and_idempotent_replay(self, mock_process: AsyncMock) -> None:
        mock_process.return_value = ("assistant reply", [])
        sid = self._create_session()
        client_id = "11111111-2222-4333-8444-555555555555"
        first = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "hello once", "client_message_id": client_id},
        )
        self.assertEqual(first.status_code, 201)
        body = first.json()
        user = next(m for m in body["messages"] if m["role"] == "user")
        self.assertEqual(
            body["user_message_acked"],
            {"message_id": int(user["id"]), "client_message_id": client_id},
        )
        self.assertEqual(user["client_message_id"], client_id)
        self.assertEqual(mock_process.await_count, 1)

        # Simulate Cursor having finished (mock does not persist assistant itself).
        import asyncio
        from utils.db_helpers import get_db

        async def _add_assistant() -> None:
            db = await get_db()
            await db.add_message(int(sid), "assistant", "assistant reply")

        asyncio.run(_add_assistant())

        second = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "hello once", "client_message_id": client_id},
        )
        self.assertEqual(second.status_code, 201)
        second_body = second.json()
        self.assertEqual(
            second_body["user_message_acked"]["message_id"],
            body["user_message_acked"]["message_id"],
        )
        users_after = [m for m in second_body["messages"] if m["role"] == "user"]
        self.assertEqual(len(users_after), 1)
        # Existing assistant after the user turn → skip Cursor on replay.
        self.assertEqual(mock_process.await_count, 1)

    @patch("kb_app_api.routes.messages.QueryProcessingService.process_query_for_api", new_callable=AsyncMock)
    def test_compose_sse_emits_ack_before_processing(self, mock_process: AsyncMock) -> None:
        started = __import__("threading").Event()

        async def slow_process(*_args, **_kwargs):
            started.wait(timeout=2)
            return ("ok", [])

        mock_process.side_effect = slow_process
        sid = self._create_session()
        client_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        with self.client.stream(
            "POST",
            f"/api/sessions/{sid}/messages/compose",
            headers={**self.headers, "Accept": "text/event-stream"},
            data={"content": "stream me", "client_message_id": client_id},
        ) as response:
            self.assertEqual(response.status_code, 200)
            events: list[dict] = []
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                payload = json.loads(line[6:])
                events.append(payload)
                if "user_message_acked" in payload:
                    started.set()
                if payload.get("done") is True:
                    break
        self.assertGreaterEqual(len(events), 2)
        self.assertIn("user_message_acked", events[0])
        self.assertEqual(events[0]["user_message_acked"]["client_message_id"], client_id)
        self.assertEqual(events[1].get("status"), "processing")
        mock_process.assert_awaited()

    def test_file_type_for_upload_sniffs_png_and_rejects_plain(self) -> None:
        from kb_app_api.routes.messages import _file_type_for_upload

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        self.assertEqual(_file_type_for_upload("shot.57_PM", png), "photo")
        self.assertEqual(
            _file_type_for_upload("x.bin", b"hello", content_type="image/png"),
            "photo",
        )
        self.assertEqual(_file_type_for_upload("note.txt", b"hello"), "document")


if __name__ == "__main__":
    smoke.setUpModule()
    unittest.main()
