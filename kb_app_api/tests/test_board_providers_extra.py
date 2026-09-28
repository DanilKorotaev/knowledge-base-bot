"""Tests for system / remote / vault_script board providers."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
    os.environ["KB_APP_API_TOKEN"] = "boards-providers-test"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000088"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    Path(_kb_dir).mkdir(parents=True, exist_ok=True)


class TestBoardProvidersExtra(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from config import config
        import utils.db_helpers as db_helpers

        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])
        config.BOARDS_REMOTE_HOST_ALLOWLIST = ["example.test"]
        db_helpers._db_instance = None  # type: ignore[attr-defined]

    def test_vault_json_charts(self) -> None:
        from kb_app_api.boards.providers import vault_json_daily_agg

        root = Path(os.environ["LOCAL_KB_PATH"])
        daily = root / "Daily"
        daily.mkdir(parents=True, exist_ok=True)
        (daily / "2026-09-01.json").write_text(
            json.dumps({"date": "2026-09-01", "steps": 1000}), encoding="utf-8"
        )
        (daily / "2026-09-02.json").write_text(
            json.dumps({"date": "2026-09-02", "steps": 2000}), encoding="utf-8"
        )
        out = vault_json_daily_agg.compute(
            root,
            {"id": "health", "title": "Health", "kind": "cached_view", "sort_order": 1},
            {
                "provider": "vault_json_daily_agg",
                "path": "Daily",
                "period_ui": "none",
                "metrics": [{"id": "steps", "field": "steps", "agg": "sum", "label": "Steps"}],
                "charts": [{"id": "steps_chart", "field": "steps", "label": "Steps"}],
                "labels": {"title": "Health"},
            },
        )
        screen = out["document"]["screen"]
        charts = [c for c in screen["children"] if c.get("type") == "chart"]
        self.assertEqual(len(charts), 1)
        self.assertEqual(len(charts[0]["series"]), 2)

    def test_vault_script(self) -> None:
        from kb_app_api.boards.providers import vault_script

        root = Path(os.environ["LOCAL_KB_PATH"])
        scripts = root / "Boards"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "demo.board.py").write_text(
            "def build(ctx):\n"
            "    return [{\"type\": \"metric\", \"id\": \"m\", \"label\": \"N\", \"text\": str(len(ctx.labels))}]\n",
            encoding="utf-8",
        )
        out = vault_script.compute(
            root,
            {"id": "scripted", "title": "Scripted", "kind": "cached_view", "sort_order": 2},
            {
                "provider": "vault_script",
                "script_path": "Boards/demo.board.py",
                "period_ui": "none",
                "labels": {"title": "Scripted", "a": "1"},
            },
        )
        children = out["document"]["screen"]["children"]
        metrics = [c for c in children if c.get("type") == "metric"]
        self.assertEqual(metrics[0]["text"], "2")

    def test_vault_script_json_and_shell(self) -> None:
        from kb_app_api.boards.providers import vault_script

        root = Path(os.environ["LOCAL_KB_PATH"])
        scripts = root / "Boards"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "demo.board.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "screen": {
                        "type": "vstack",
                        "id": "root",
                        "children": [{"type": "text", "id": "t", "text": "from-json"}],
                    },
                }
            ),
            encoding="utf-8",
        )
        (scripts / "demo.board.sh").write_text(
            "#!/bin/bash\necho '{\"schema_version\":1,\"screen\":{\"type\":\"vstack\",\"id\":\"root\",\"children\":[{\"type\":\"text\",\"id\":\"t\",\"text\":\"from-sh\"}]}}'\n",
            encoding="utf-8",
        )
        out_json = vault_script.compute(
            root,
            {"id": "j", "title": "J", "kind": "cached_view", "sort_order": 1},
            {"provider": "vault_script", "script_path": "Boards/demo.board.json"},
        )
        self.assertIn("from-json", str(out_json["document"]))
        out_sh = vault_script.compute(
            root,
            {"id": "s", "title": "S", "kind": "cached_view", "sort_order": 2},
            {"provider": "vault_script", "script_path": "Boards/demo.board.sh"},
        )
        self.assertIn("from-sh", str(out_sh["document"]))

    def test_remote_allowlist(self) -> None:
        from kb_app_api.boards.providers import remote_structured_ui

        blocked = remote_structured_ui.compute(
            {"id": "remote", "title": "R", "kind": "remote", "sort_order": 3},
            {"provider": "remote_structured_ui", "url": "https://evil.example/board.json"},
        )
        err = blocked["document"]["screen"]["children"][1]["text"]
        self.assertIn("allowlist", err.lower())

        payload = {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [{"type": "text", "id": "t", "text": "Hi"}],
            },
        }

        def fake_fetch(url: str, *, timeout: float):
            _ = timeout
            self.assertEqual(url, "https://example.test/board.json")
            return payload

        with patch.object(remote_structured_ui, "_fetch_json", side_effect=fake_fetch):
            ok = remote_structured_ui.compute(
                {"id": "remote", "title": "R", "kind": "remote", "sort_order": 3},
                {
                    "provider": "remote_structured_ui",
                    "url": "https://example.test/board.json",
                    "labels": {"title": "Remote"},
                },
            )
        self.assertEqual(ok["document"]["screen"]["children"][0]["text"], "Hi")

    def test_system_query_jobs_empty(self) -> None:
        async def _run() -> None:
            from utils.db_helpers import get_db
            from kb_app_api.boards.providers import system_query_jobs

            db = await get_db()
            user = await db.ensure_user(9000000009000088, "boards-prov")
            out = await system_query_jobs.compute(
                {"id": "active-jobs", "title": "Jobs", "kind": "system", "sort_order": 0},
                {
                    "provider": "system_query_jobs",
                    "labels": {"title": "Jobs", "empty": "None"},
                },
                user_id=int(user["id"]),
            )
            texts = [c.get("text") for c in out["document"]["screen"]["children"]]
            self.assertIn("None", texts)

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
