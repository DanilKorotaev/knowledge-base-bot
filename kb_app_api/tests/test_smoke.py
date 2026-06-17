"""
Smoke-тесты HTTP без реального Cursor/Nextcloud.

Требуется окружение с зависимостями бота (`pip install -r requirements.txt`).

Запуск из корня knowledge-base-bot::

    python -m unittest kb_app_api.tests.test_smoke -v

Или: ``pytest kb_app_api/tests/test_smoke.py -q`` (нужен ``pip install pytest``).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_db_file: str | None = None
_kb_dir: str | None = None


def setUpModule() -> None:
    global _db_file, _kb_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_API_TOKEN"] = "smoke-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000001"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    Path(_kb_dir).mkdir(parents=True, exist_ok=True)


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestKbAppApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)

    def test_health_ok(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("status"), "ok")

    def test_sessions_require_bearer(self) -> None:
        r = self.client.get("/api/sessions")
        self.assertEqual(r.status_code, 401)

    def test_sessions_with_bearer_empty(self) -> None:
        r = self.client.get(
            "/api/sessions",
            headers={"Authorization": "Bearer smoke-test-bearer"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("sessions", data)
        self.assertIsInstance(data["sessions"], list)

    def test_create_session(self) -> None:
        r = self.client.post(
            "/api/sessions",
            headers={"Authorization": "Bearer smoke-test-bearer"},
            json={"title": "Smoke"},
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertIn("session", body)
        self.assertIn("id", body["session"])

    def test_messages_include_content_format(self) -> None:
        create = self.client.post(
            "/api/sessions",
            headers={"Authorization": "Bearer smoke-test-bearer"},
            json={"title": "Rich"},
        )
        sid = create.json()["session"]["id"]

        from utils.db_helpers import get_db

        import asyncio

        async def seed() -> None:
            db = await get_db()
            user_msg = await db.add_message(int(sid), "user", "hello")
            await db.add_message(int(sid), "assistant", "**bold** reply")
            img_path = Path(_kb_dir or "") / "test.jpg"
            img_path.write_bytes(b"fake-image")
            await db.add_attachment(
                session_id=int(sid),
                message_id=int(user_msg["id"]),
                file_type="photo",
                file_id="local:test",
                file_path=str(img_path),
                file_name="test.jpg",
                file_size=10,
            )

        asyncio.run(seed())

        r = self.client.get(
            f"/api/sessions/{sid}/messages",
            headers={"Authorization": "Bearer smoke-test-bearer"},
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("messages", data)
        msgs = data["messages"]
        self.assertGreaterEqual(len(msgs), 2)
        assistant = next(m for m in msgs if m["role"] == "assistant")
        self.assertEqual(assistant.get("content_format"), "markdown")
        user = next(m for m in msgs if m["role"] == "user")
        self.assertEqual(user.get("content_format"), "plain")
        self.assertIn("attachments", user)
        self.assertEqual(user["attachments"][0]["file_type"], "photo")

    def test_attachment_file_requires_auth(self) -> None:
        r = self.client.get("/api/sessions/1/attachments/1/file")
        self.assertEqual(r.status_code, 401)

    def test_voice_transcribe_requires_bearer(self) -> None:
        r = self.client.post(
            "/api/query/voice/transcribe",
            files={"audio": ("note.m4a", b"\x00\x01", "audio/mp4")},
        )
        self.assertEqual(r.status_code, 401)

    def test_voice_transcribe_rejects_empty_audio(self) -> None:
        r = self.client.post(
            "/api/query/voice/transcribe",
            headers={"Authorization": "Bearer smoke-test-bearer"},
            files={"audio": ("note.m4a", b"", "audio/mp4")},
        )
        self.assertEqual(r.status_code, 422)

    def test_voice_message_requires_bearer(self) -> None:
        r = self.client.post(
            "/api/sessions/1/messages/voice",
            files={"audio": ("note.m4a", b"\x00", "audio/mp4")},
            data={"content": "hello"},
        )
        self.assertEqual(r.status_code, 401)

    def test_voice_message_rejects_empty_content(self) -> None:
        headers = {"Authorization": "Bearer smoke-test-bearer"}
        create = self.client.post("/api/sessions", headers=headers, json={"title": "Voice msg"})
        sid = create.json()["session"]["id"]
        r = self.client.post(
            f"/api/sessions/{sid}/messages/voice",
            headers=headers,
            files={"audio": ("note.m4a", b"\x00\x01", "audio/mp4")},
            data={"content": "   "},
        )
        self.assertEqual(r.status_code, 422)

    def test_delete_and_patch_session(self) -> None:
        headers = {"Authorization": "Bearer smoke-test-bearer"}
        create = self.client.post(
            "/api/sessions",
            headers=headers,
            json={"title": "To mutate"},
        )
        self.assertEqual(create.status_code, 201)
        sid = create.json()["session"]["id"]

        patch = self.client.patch(
            f"/api/sessions/{sid}",
            headers=headers,
            json={"title": "Renamed"},
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.json()["session"]["title"], "Renamed")

        listed = self.client.get("/api/sessions", headers=headers)
        ids = [s["id"] for s in listed.json()["sessions"]]
        self.assertIn(sid, ids)

        delete = self.client.delete(f"/api/sessions/{sid}", headers=headers)
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(delete.json().get("success"))

        listed_after = self.client.get("/api/sessions", headers=headers)
        ids_after = [s["id"] for s in listed_after.json()["sessions"]]
        self.assertNotIn(sid, ids_after)

    def test_file_share_link_endpoint_requires_nextcloud(self) -> None:
        headers = {"Authorization": "Bearer smoke-test-bearer"}
        create = self.client.post(
            "/api/sessions",
            headers=headers,
            json={"title": "Files share"},
        )
        self.assertEqual(create.status_code, 201)
        sid = create.json()["session"]["id"]

        from utils.db_helpers import get_db

        import asyncio

        async def seed() -> str:
            db = await get_db()
            row = await db.log_file_change(
                session_id=int(sid),
                file_path="notes/share.md",
                change_type="modified",
                old_content="before",
                new_content="after",
            )
            return str(row["id"])

        change_id = asyncio.run(seed())

        response = self.client.post(
            "/api/files/share-link",
            headers=headers,
            json={"file_id": change_id},
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body.get("error", {}).get("code"), "nextcloud_unavailable")


if __name__ == "__main__":
    unittest.main()
