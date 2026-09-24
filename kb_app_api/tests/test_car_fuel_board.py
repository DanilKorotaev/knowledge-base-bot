"""vault_frontmatter_agg provider + boards DB runtime."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from kb_app_api.boards.providers import vault_frontmatter_agg as agg
from kb_app_api.boards.vault_io import VaultReadError, resolve_under_root


class VaultFrontmatterAggTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        fuel = self.root / "Документы" / "Тачки" / "Соляра" / "Расходы" / "Топливо"
        fuel.mkdir(parents=True)
        (fuel / "2026-09-11.md").write_text(
            "---\n"
            "type: fuel\n"
            "date: 2026-09-11\n"
            "liters: 40\n"
            "cost: 2996\n"
            'station: "[[Роснефть]]"\n'
            "---\n",
            encoding="utf-8",
        )
        (fuel / "2026-08-01.md").write_text(
            "---\ntype: fuel\ndate: 2026-08-01\nliters: 20\ncost: 1500\nstation: Teboil\n---\n",
            encoding="utf-8",
        )
        self.guard = fuel / "2026-09-11.md"
        self.guard_bytes = self.guard.read_bytes()
        self.guard_mtime = self.guard.stat().st_mtime_ns
        self.definition = {
            "provider": "vault_frontmatter_agg",
            "path": "Документы/Тачки/Соляра/Расходы/Топливо",
            "filter": {"type": "fuel"},
            "fields": {"date": "date", "amount": "cost", "quantity": "liters", "label": "station"},
            "recent_limit": 10,
            "labels": {
                "title": "Соляра — топливо",
                "list_title": "Авторасходы — топливо",
                "metric_month": "Этот месяц",
                "currency": "₽",
            },
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_and_compute_read_only(self) -> None:
        meta = {"id": "car-fuel", "title": "Авторасходы — топливо", "kind": "cached_view", "sort_order": 5}
        payload = agg.compute(self.root, meta, self.definition)
        self.assertEqual(payload["board"]["id"], "car-fuel")
        table = next(n for n in payload["document"]["screen"]["children"] if n.get("type") == "table")
        self.assertEqual(table.get("scroll_horizontal"), False)
        self.assertEqual(self.guard.read_bytes(), self.guard_bytes)
        self.assertEqual(self.guard.stat().st_mtime_ns, self.guard_mtime)

    def test_nested_computed_fields_workouts(self) -> None:
        workouts = self.root / "Тренировки" / "2026" / "Сентябрь"
        workouts.mkdir(parents=True)
        note = workouts / "2026-09-23.md"
        note.write_text(
            "---\n"
            "type: workout\n"
            "date: 2026-09-23\n"
            "focus: грудь\n"
            "computed:\n"
            "  total_volume_kg: 5965.72\n"
            "  total_sets: 18\n"
            "---\n",
            encoding="utf-8",
        )
        before = note.read_bytes()
        mtime = note.stat().st_mtime_ns
        definition = {
            "provider": "vault_frontmatter_agg",
            "path": "Тренировки",
            "filter": {"type": "workout"},
            "fields": {
                "date": "date",
                "amount": "computed.total_volume_kg",
                "quantity": "computed.total_sets",
                "label": "focus",
            },
            "labels": {"title": "Тренировки", "currency": "кг"},
        }
        entries = agg.load_entries(self.root, definition)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].label, "грудь")
        self.assertAlmostEqual(entries[0].amount, 5965.72)
        self.assertEqual(entries[0].quantity, 18.0)
        payload = agg.compute(
            self.root,
            {"id": "workouts", "title": "Тренировки", "kind": "cached_view", "sort_order": 10},
            definition,
        )
        table = next(n for n in payload["document"]["screen"]["children"] if n.get("type") == "table")
        self.assertEqual(table["rows"][0][1], "грудь")
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(note.stat().st_mtime_ns, mtime)

    def test_path_required_from_definition(self) -> None:
        entries = agg.load_entries(self.root, {"path": "", "filter": {"type": "fuel"}})
        self.assertEqual(entries, [])

    def test_escape_blocked(self) -> None:
        with self.assertRaises(VaultReadError):
            resolve_under_root(self.root, "../outside")


class BoardsRuntimeAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._fd, self._db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(self._fd)
        self._kb = tempfile.mkdtemp()
        fuel = Path(self._kb) / "Документы" / "Тачки" / "Соляра" / "Расходы" / "Топливо"
        fuel.mkdir(parents=True)
        (fuel / "one.md").write_text(
            "---\ntype: fuel\ndate: 2026-09-01\ncost: 100\nliters: 1\nstation: A\n---\n",
            encoding="utf-8",
        )
        os.environ["DB_TYPE"] = "sqlite"
        os.environ["DB_FILE"] = self._db_path
        os.environ["LOCAL_KB_PATH"] = self._kb
        import config as config_mod

        config_mod.config.DB_TYPE = "sqlite"
        config_mod.config.DB_FILE = self._db_path
        config_mod.config.LOCAL_KB_PATH = Path(self._kb)

        # Reset schema flag between tests.
        import kb_app_api.boards.repository as repo

        repo._SCHEMA_READY = False  # noqa: SLF001

        from utils.db_helpers import close_db

        await close_db()

    async def asyncTearDown(self) -> None:
        from utils.db_helpers import close_db

        await close_db()
        try:
            os.unlink(self._db_path)
        except OSError:
            pass

    async def test_list_includes_seeded_car_fuel(self) -> None:
        from kb_app_api.boards_catalog import get_board_detail, list_boards

        boards = await list_boards()
        ids = [b["id"] for b in boards]
        self.assertIn("car-fuel", ids)
        self.assertIn("demo-kpi", ids)
        self.assertIn("workouts", ids)
        detail = await get_board_detail("car-fuel")
        assert detail is not None
        self.assertEqual(detail["document"]["schema_version"], 1)
        workouts = await get_board_detail("workouts")
        assert workouts is not None
        self.assertEqual(workouts["board"]["id"], "workouts")


if __name__ == "__main__":
    unittest.main()
