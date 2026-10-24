"""Auth register/login/refresh/me (sqlite, no Nextcloud)."""
from __future__ import annotations

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


def setUpModule() -> None:
    global _db_file, _kb_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_JWT_SECRET"] = "auth-unit-jwt"
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["LOCAL_KB_PATH"] = _kb_dir


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


@unittest.skipUnless(TestClient is not None, "fastapi required")
class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)

    def test_register_login_refresh_me(self) -> None:
        r = self.client.post(
            "/api/auth/register",
            json={"login": "alice", "password": "password123", "email": "a@ex.com"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["user"]["login"], "alice")
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        me = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["user"]["login"], "alice")

        refreshed = self.client.post(
            "/api/auth/refresh",
            json={"refresh_token": body["refresh_token"]},
        )
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        self.assertIn("access_token", refreshed.json())

        login = self.client.post(
            "/api/auth/login",
            json={"login": "alice", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200)

    def test_sessions_isolated_by_user(self) -> None:
        a = self.client.post(
            "/api/auth/register",
            json={"login": "bob", "password": "password123"},
        )
        self.assertEqual(a.status_code, 200, a.text)
        ah = {"Authorization": f"Bearer {a.json()['access_token']}"}
        s = self.client.post("/api/sessions", headers=ah, json={"title": "Bob only"})
        self.assertEqual(s.status_code, 201)

        c = self.client.post(
            "/api/auth/register",
            json={"login": "carol", "password": "password123"},
        )
        self.assertEqual(c.status_code, 200, c.text)
        ch = {"Authorization": f"Bearer {c.json()['access_token']}"}
        listed = self.client.get("/api/sessions", headers=ch)
        self.assertEqual(listed.status_code, 200)
        titles = [x.get("title") or x.get("display_title") for x in listed.json()["sessions"]]
        self.assertNotIn("Bob only", titles)
