"""Crash log upload, admin switch, and join with a prior crash report."""
from __future__ import annotations

import gzip
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_db_file: str | None = None
_kb_dir: str | None = None
_log_dir: str | None = None


def setUpModule() -> None:
    global _db_file, _kb_dir, _log_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    _log_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_JWT_SECRET"] = "crash-log-test-jwt"
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    os.environ["KB_CRASH_LOG_DIR"] = _log_dir


@unittest.skipUnless(TestClient is not None, "fastapi required")
class TestCrashLogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import asyncio

        from kb_app_api import auth_service
        from kb_app_api.main import app
        from kb_app_api.tests.auth_test_helpers import bearer_headers
        from utils.db_helpers import get_db

        cls.client = TestClient(app)

        async def _mk_admin() -> None:
            db = await get_db()
            await auth_service.register_user(
                db,
                login="crashadmin",
                password="password123",
                role="admin",
                is_admin=True,
                signup_source="test",
                provision_nc=False,
            )

        asyncio.run(_mk_admin())
        cls.admin = bearer_headers(cls.client, login="crashadmin", password="password123")
        cls.user = bearer_headers(cls.client, login="crashuser", password="password123", email="crash@example.com")

    def test_upload_and_admin_download(self) -> None:
        session = "11111111-2222-3333-4444-555555555555"
        response = self.client.post(
            "/api/crash-logs",
            headers=self.user,
            data={"log_session": session, "app_version": "2.0.15", "app_build": "276"},
            files={"file": ("session.log", b"app started\nboom\n", "text/plain")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["followup"])
        downloaded = self.client.get(f"/api/admin/crash-logs/{session}", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertIn(b"boom", downloaded.content)
        forbidden = self.client.get(f"/api/admin/crash-logs/{session}", headers=self.user)
        self.assertEqual(forbidden.status_code, 403, forbidden.text)

    def test_gzip_upload_is_stored_plain(self) -> None:
        session = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        response = self.client.post(
            "/api/crash-logs",
            headers=self.user,
            data={"log_session": session, "app_version": "2.0.15", "app_build": "276"},
            files={"file": ("session.log.gz", gzip.compress(b"app started\npacked\n"), "application/gzip")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        downloaded = self.client.get(f"/api/admin/crash-logs/{session}", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200, downloaded.text)
        self.assertIn(b"packed", downloaded.content)

    def test_switch_rejects_upload(self) -> None:
        off = self.client.patch(
            "/api/admin/settings",
            headers=self.admin,
            json={"accept_crash_logs": False},
        )
        self.assertEqual(off.status_code, 200, off.text)
        response = self.client.post(
            "/api/crash-logs",
            headers=self.user,
            data={"log_session": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
            files={"file": ("session.log", b"nope\n", "text/plain")},
        )
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"]["code"], "crash_logs_disabled")
        on = self.client.patch(
            "/api/admin/settings",
            headers=self.admin,
            json={"accept_crash_logs": True},
        )
        self.assertEqual(on.status_code, 200, on.text)

    def test_file_after_crash_posts_followup(self) -> None:
        import asyncio

        from kb_app_api.crash_logs.store import note_crash_delivery
        from utils.db_helpers import get_db

        created = self.client.post(
            "/api/sessions",
            headers=self.user,
            json={"title": "Crashes", "use_knowledge_base": False},
        )
        self.assertEqual(created.status_code, 201, created.text)
        chat_id = int(created.json()["session"]["id"])

        async def _uid() -> int:
            db = await get_db()
            user = await db.get_user_by_login("crashuser")
            return int(user["id"])

        uid = asyncio.run(_uid())
        session = "99999999-aaaa-bbbb-cccc-dddddddddddd"
        asyncio.run(
            note_crash_delivery(
                user_id=uid,
                log_session=session,
                chat_session_id=chat_id,
                crash_event_id="evt-1",
                logs_already_ready=False,
            )
        )
        response = self.client.post(
            "/api/crash-logs",
            headers=self.user,
            data={"log_session": session, "app_version": "2.0.15", "app_build": "276"},
            files={"file": ("session.log", b"line\n", "text/plain")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["followup"])


class TestTypeListMatch(unittest.TestCase):
    def test_type_list(self) -> None:
        from kb_app_api.ingress.router import _match_rule

        match = {"source": "ios", "type": ["app.crash", "app.crash_logs"]}
        self.assertTrue(
            _match_rule(match, {"source": "ios", "type": "app.crash_logs"}, {"channel_id": "default"})
        )
        self.assertFalse(
            _match_rule(match, {"source": "ios", "type": "other"}, {"channel_id": "default"})
        )
