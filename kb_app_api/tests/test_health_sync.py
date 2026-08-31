"""
Tests for HealthKit sync routes and user settings.
"""
from __future__ import annotations

import base64
import json
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
    os.environ["KB_APP_API_TOKEN"] = "health-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000002"
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
class TestHealthSyncApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer health-test-bearer"}

    def test_settings_default(self) -> None:
        response = self.client.get("/api/me/settings", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["health_data_relative"], "HealthData")

    def test_settings_patch_valid(self) -> None:
        response = self.client.patch(
            "/api/me/settings",
            headers=self.headers,
            json={"health_data_relative": "HealthData/custom"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["health_data_relative"], "HealthData/custom")

    def test_settings_patch_rejects_traversal(self) -> None:
        response = self.client.patch(
            "/api/me/settings",
            headers=self.headers,
            json={"health_data_relative": "../secrets"},
        )
        self.assertEqual(response.status_code, 422)

    def test_sync_files_writes_under_health_root(self) -> None:
        payload = {"date": "2026-01-01", "steps": 1000}
        body_bytes = json.dumps(payload).encode("utf-8")
        response = self.client.post(
            "/api/health/sync/files",
            headers=self.headers,
            json={
                "files": [
                    {
                        "path": "daily/2026-01-01.json",
                        "content_base64": base64.b64encode(body_bytes).decode("ascii"),
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["written"], ["daily/2026-01-01.json"])
        self.assertFalse(data["synced_to_nextcloud"])

        written = Path(_kb_dir or "") / "HealthData" / "daily" / "2026-01-01.json"
        self.assertTrue(written.is_file())
        self.assertEqual(json.loads(written.read_text(encoding="utf-8")), payload)

    def test_sync_state_not_found(self) -> None:
        response = self.client.get("/api/health/sync/state", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_sync_state_returns_json(self) -> None:
        state = {"last_synced_at": "2026-01-01T00:00:00Z"}
        state_path = Path(_kb_dir or "") / "HealthData" / "sync_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state), encoding="utf-8")

        response = self.client.get("/api/health/sync/state", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), state)


if __name__ == "__main__":
    unittest.main()
