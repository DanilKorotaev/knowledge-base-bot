"""Admin users API (sqlite)."""
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
    os.environ["KB_APP_JWT_SECRET"] = "admin-test-jwt"
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["LOCAL_KB_PATH"] = _kb_dir


@unittest.skipUnless(TestClient is not None, "fastapi required")
class TestAdminUsers(unittest.TestCase):
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
                login="superadmin",
                password="password123",
                role="admin",
                is_admin=True,
                signup_source="test",
                provision_nc=False,
            )

        asyncio.run(_mk_admin())
        cls.headers = bearer_headers(cls.client, login="superadmin", password="password123")

    def test_list_and_create(self) -> None:
        listed = self.client.get("/api/admin/users", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        created = self.client.post(
            "/api/admin/users",
            headers=self.headers,
            json={"login": "newbie", "role": "user", "cursor_isolation": "host"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()["user"]
        self.assertEqual(body["login"], "newbie")
        self.assertEqual(body["cursor_isolation"], "host")
        self.assertIn("temporary_password", body)

    def test_non_admin_forbidden(self) -> None:
        from kb_app_api.tests.auth_test_helpers import bearer_headers

        user_h = bearer_headers(self.client, login="plainuser", password="password123")
        r = self.client.get("/api/admin/users", headers=user_h)
        self.assertEqual(r.status_code, 403)
