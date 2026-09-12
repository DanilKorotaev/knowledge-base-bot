"""Tests for fast sessions list (message_count without loading message bodies)."""
from __future__ import annotations

import os
import sys
import tempfile
import time
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
    os.environ["KB_APP_API_TOKEN"] = "sessions-perf-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000099"
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
class TestSessionsListPerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer sessions-perf-bearer"}

    def test_list_sessions_message_count_without_loading_bodies(self) -> None:
        create = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Perf list"},
        )
        self.assertEqual(create.status_code, 201)
        sid = create.json()["session"]["id"]

        from utils.db_helpers import get_db
        import asyncio

        async def seed() -> None:
            db = await get_db()
            for i in range(200):
                await db.add_message(int(sid), "user", f"msg body {i} " + ("x" * 200))

        asyncio.run(seed())

        t0 = time.perf_counter()
        listed = self.client.get("/api/sessions?per_page=20", headers=self.headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        match = next(s for s in body["sessions"] if s["id"] == sid)
        self.assertEqual(match["message_count"], 200)
        # SQLite smoke budget; real PG on mini is the acceptance target.
        self.assertLess(elapsed_ms, 500.0, f"list too slow: {elapsed_ms:.1f}ms")

    def test_search_by_message_text_uses_counts(self) -> None:
        create = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Searchable"},
        )
        sid = create.json()["session"]["id"]
        from utils.db_helpers import get_db
        import asyncio

        async def seed() -> None:
            db = await get_db()
            await db.add_message(int(sid), "user", "unique-token-xyz-42")

        asyncio.run(seed())
        r = self.client.get(
            "/api/sessions/search",
            headers=self.headers,
            params={"q": "unique-token-xyz-42"},
        )
        self.assertEqual(r.status_code, 200)
        sessions = r.json()["sessions"]
        self.assertTrue(any(s["id"] == sid for s in sessions))
        self.assertEqual(next(s for s in sessions if s["id"] == sid)["message_count"], 1)


class TestSessionToKbFromRow(unittest.TestCase):
    def test_from_row_uses_session_updated_at(self) -> None:
        from kb_app_api.serializers import session_to_kb_from_row

        out = session_to_kb_from_row(
            {
                "id": 7,
                "display_title": "T",
                "session_type": "query_with_kb",
                "updated_at": "2026-06-01T12:00:00Z",
                "created_at": "2026-05-01T12:00:00Z",
            },
            12,
        )
        self.assertEqual(out["message_count"], 12)
        self.assertEqual(out["id"], "7")
        self.assertIn("2026-06-01", out["updated_at"])


if __name__ == "__main__":
    unittest.main()
