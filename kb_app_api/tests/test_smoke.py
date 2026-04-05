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


if __name__ == "__main__":
    unittest.main()
