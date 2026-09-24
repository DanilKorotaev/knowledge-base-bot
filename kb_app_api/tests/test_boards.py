"""Boards HTTP routes + catalog."""
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
    os.environ["KB_APP_API_TOKEN"] = "boards-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000003"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    Path(_kb_dir).mkdir(parents=True, exist_ok=True)


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


class BoardsCatalogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        import config as config_mod
        import kb_app_api.boards.repository as repo
        from utils.db_helpers import close_db

        config_mod.config.DB_TYPE = "sqlite"
        config_mod.config.DB_FILE = _db_file
        config_mod.config.LOCAL_KB_PATH = Path(_kb_dir or ".")
        repo._SCHEMA_READY = False  # noqa: SLF001
        await close_db()

    async def test_list_sorted_enabled(self) -> None:
        from kb_app_api.boards_catalog import list_boards

        boards = await list_boards()
        self.assertGreaterEqual(len(boards), 2)
        ids = [b["id"] for b in boards]
        self.assertIn("demo-kpi", ids)
        demo_idx = ids.index("demo-kpi")
        jobs_idx = ids.index("demo-active-jobs")
        self.assertLess(demo_idx, jobs_idx)

    async def test_detail_has_metric_and_table(self) -> None:
        from kb_app_api.boards_catalog import get_board_detail

        detail = await get_board_detail("demo-kpi")
        assert detail is not None
        screen = detail["document"]["screen"]
        flat_types: list[str] = []

        def walk(node: dict) -> None:
            flat_types.append(node["type"])
            for child in node.get("children") or []:
                walk(child)

        walk(screen)
        self.assertIn("metric", flat_types)
        self.assertIn("table", flat_types)
        self.assertIsNone(await get_board_detail("missing"))


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class BoardsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import config as config_mod
        import kb_app_api.boards.repository as repo

        os.environ["ACCESS_MODE"] = "open"
        os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"
        config_mod.config.KB_APP_API_TOKEN = "boards-test-bearer"
        config_mod.config.KB_APP_API_TELEGRAM_ID = 9000000009000003
        config_mod.config.DB_TYPE = "sqlite"
        config_mod.config.ACCESS_MODE = "open"
        config_mod.config.KB_APP_API_BYPASS_ACCESS_CHECK = True
        if _db_file:
            config_mod.config.DB_FILE = _db_file
        if _kb_dir:
            config_mod.config.LOCAL_KB_PATH = Path(_kb_dir)
        repo._SCHEMA_READY = False  # noqa: SLF001

        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer boards-test-bearer"}

    def test_list_boards(self) -> None:
        response = self.client.get("/api/boards", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 2)
        ids = [b["id"] for b in payload["boards"]]
        self.assertIn("demo-kpi", ids)
        self.assertIn("car-fuel", ids)
        self.assertIn("workouts", ids)

    def test_get_board_detail(self) -> None:
        response = self.client.get("/api/boards/demo-kpi", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["board"]["id"], "demo-kpi")
        self.assertEqual(payload["document"]["schema_version"], 1)

    def test_get_board_missing(self) -> None:
        response = self.client.get("/api/boards/nope", headers=self.headers)
        self.assertEqual(response.status_code, 404)

    def test_refresh_board(self) -> None:
        response = self.client.post("/api/boards/demo-active-jobs/refresh", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["board"]["kind"], "system")

    def test_unauthorized(self) -> None:
        response = self.client.get("/api/boards")
        self.assertIn(response.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
