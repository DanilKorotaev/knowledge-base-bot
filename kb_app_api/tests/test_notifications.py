"""User notification inbox API."""
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
from kb_app_api.tests.auth_test_helpers import bearer_headers  # noqa: E402


def setUpModule() -> None:
    smoke.setUpModule()
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"


def tearDownModule() -> None:
    smoke.tearDownModule()


@unittest.skipUnless(TestClient is not None, "Нужен fastapi")
class TestNotificationsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from config import config

        config.KB_APP_JWT_SECRET = os.environ.get("KB_APP_JWT_SECRET", "smoke-test-jwt-secret")
        config.ACCESS_MODE = "open"
        config.KB_APP_API_BYPASS_ACCESS_CHECK = True
        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])
        config.KB_APP_QUERY_JOBS_ENABLED = False

        import utils.db_helpers as db_helpers

        db_helpers._db_instance = None  # type: ignore[attr-defined]

        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = bearer_headers(cls.client, login="notif_tester")

    def test_create_list_read_and_dedupe(self) -> None:
        import asyncio

        from kb_app_api.notifications import store
        from kb_app_api.notifications.schema import ensure_notifications_schema

        async def _seed() -> int:
            await ensure_notifications_schema()
            # Resolve user id via /api/auth/me if present, else list after create.
            return 0

        asyncio.run(_seed())

        me = self.client.get("/api/auth/me", headers=self.headers)
        if me.status_code != 200:
            me = self.client.get("/api/me/settings", headers=self.headers)
        self.assertIn(me.status_code, (200,), me.text)

        # Create via store with user from JWT path: create notification through service after session
        session = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Notif target"},
        )
        self.assertEqual(session.status_code, 201, session.text)
        session_id = int(session.json()["session"]["id"])

        async def _insert() -> None:
            from utils.db_helpers import get_db

            db = await get_db()
            # Find user_id from session
            s = await db.get_session(session_id)
            uid = int(s["user_id"])
            first = await store.create_notification(
                user_id=uid,
                kind="ingress_event",
                title="Disk almost full",
                body="P1",
                source_key="grafana",
                session_id=session_id,
                message_id=1,
                event_id="evt-1",
                dedupe_key="ingress:evt-1",
            )
            self.assertIsNotNone(first)
            dup = await store.create_notification(
                user_id=uid,
                kind="ingress_event",
                title="Disk almost full again",
                body="P1",
                source_key="grafana",
                session_id=session_id,
                message_id=2,
                event_id="evt-1",
                dedupe_key="ingress:evt-1",
            )
            self.assertIsNone(dup)
            await store.create_notification(
                user_id=uid,
                kind="agent_reply",
                title="Notif target",
                body="Done",
                source_key="agent",
                session_id=session_id,
                message_id=3,
                dedupe_key=f"agent_reply:{session_id}:3",
            )

        asyncio.run(_insert())

        listed = self.client.get("/api/me/notifications", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        body = listed.json()
        self.assertGreaterEqual(body["unread_count"], 2)
        notes = body["notifications"]
        self.assertGreaterEqual(len(notes), 2)
        kinds = {n["kind"] for n in notes}
        self.assertIn("ingress_event", kinds)
        self.assertIn("agent_reply", kinds)

        nid = notes[0]["id"]
        read = self.client.post(f"/api/me/notifications/{nid}/read", headers=self.headers)
        self.assertEqual(read.status_code, 200, read.text)

        unread = self.client.get("/api/me/notifications/unread-count", headers=self.headers)
        self.assertEqual(unread.status_code, 200)
        self.assertLess(unread.json()["unread_count"], body["unread_count"])

        all_read = self.client.post("/api/me/notifications/read-all", headers=self.headers)
        self.assertEqual(all_read.status_code, 200, all_read.text)
        self.assertEqual(all_read.json()["unread_count"], 0)


if __name__ == "__main__":
    unittest.main()
