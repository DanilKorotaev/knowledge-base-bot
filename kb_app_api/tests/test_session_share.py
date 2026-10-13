"""Session share public links (owner Bearer + public token)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kb_app_api.tests import test_smoke as smoke  # noqa: E402


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestSessionShare(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Reuse smoke env (temp sqlite + token) from module import order.
        smoke.setUpModule()
        os.environ["KB_APP_PUBLIC_BASE_URL"] = "https://kb.example.test"
        import config as app_config

        app_config.config.KB_APP_PUBLIC_BASE_URL = "https://kb.example.test"
        app_config.config.KB_APP_SHARE_DEFAULT_TTL_DAYS = 30

        from utils import db_helpers

        db_helpers._db_instance = None  # type: ignore[attr-defined]
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer smoke-test-bearer"}

    def _create_session_with_message(self) -> str:
        created = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Share me", "use_knowledge_base": False},
        )
        self.assertEqual(created.status_code, 201, created.text)
        session_id = str(created.json()["session"]["id"])

        # Persist a user message via DB (avoid Cursor pipeline).
        import asyncio

        from utils.db_helpers import get_db

        async def _add() -> None:
            db = await get_db()
            await db.add_message(int(session_id), "user", "Hello shared world")

        asyncio.run(_add())
        return session_id

    def test_share_requires_bearer(self) -> None:
        session_id = self._create_session_with_message()
        r = self.client.post(f"/api/sessions/{session_id}/share")
        self.assertEqual(r.status_code, 401)

    def test_create_public_get_and_revoke(self) -> None:
        session_id = self._create_session_with_message()
        created = self.client.post(
            f"/api/sessions/{session_id}/share",
            headers=self.headers,
            json={},
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertTrue(body["share_url"].startswith("https://kb.example.test/share/"))
        self.assertTrue(body["api_url"].startswith("https://kb.example.test/api/share/"))
        token = body["share_url"].rsplit("/", 1)[-1]

        public = self.client.get(f"/api/share/{token}")
        self.assertEqual(public.status_code, 200, public.text)
        data = public.json()
        self.assertEqual(str(data["session"]["id"]), session_id)
        self.assertGreaterEqual(len(data["messages"]), 1)
        self.assertIn("Hello shared world", data["messages"][0]["content"])

        html = self.client.get(f"/share/{token}")
        self.assertEqual(html.status_code, 200)
        self.assertIn("text/html", html.headers.get("content-type", ""))
        self.assertIn("Hello shared world", html.text)

        revoked = self.client.delete(
            f"/api/sessions/{session_id}/share",
            headers=self.headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)
        self.assertTrue(revoked.json().get("success"))

        gone = self.client.get(f"/api/share/{token}")
        self.assertEqual(gone.status_code, 404)


if __name__ == "__main__":
    unittest.main()
