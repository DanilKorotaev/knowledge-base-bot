"""Tests for POST /api/sessions/{id}/messages/compose."""
from __future__ import annotations

import json
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


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestComposeMessage(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        self.assertEqual(response.status_code, 422)

    def test_compose_rejects_empty_file(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/messages/compose",
            headers=self.headers,
            data={"content": "see file"},
            files=[("files", ("empty.bin", b"", "application/octet-stream"))],
        )
        self.assertEqual(response.status_code, 422)

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
        self.assertEqual(response.status_code, 422)

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
        self.assertEqual(response.status_code, 422)

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


if __name__ == "__main__":
    smoke.setUpModule()
    unittest.main()
