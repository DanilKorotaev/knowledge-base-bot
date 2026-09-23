"""Read-only car fuel board compute + vault_io."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from kb_app_api.boards.car_expenses import (
    BOARD_ID,
    FuelEntry,
    build_car_fuel_document,
    compute_car_fuel_board,
    load_fuel_entries,
)
from kb_app_api.boards.vault_io import VaultReadError, iter_markdown_files, read_text_under_root, resolve_under_root


class VaultIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "safe").mkdir()
        (self.root / "safe" / "note.md").write_text("---\ntype: fuel\n---\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolve_blocks_escape(self) -> None:
        with self.assertRaises(VaultReadError):
            resolve_under_root(self.root, "../outside")

    def test_read_text(self) -> None:
        text = read_text_under_root(self.root, "safe/note.md")
        self.assertIn("type: fuel", text)

    def test_iter_markdown(self) -> None:
        files = iter_markdown_files(self.root, "safe")
        self.assertEqual(len(files), 1)


class CarFuelComputeTests(unittest.TestCase):
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
            'fuel_type: "[[АИ-95]]"\n'
            "---\n"
            "# Заправка\n",
            encoding="utf-8",
        )
        (fuel / "2026-08-01.md").write_text(
            "---\n"
            "type: fuel\n"
            "date: 2026-08-01\n"
            "liters: 20.5\n"
            "cost: 1500.5\n"
            'station: "[[Teboil]]"\n'
            "---\n",
            encoding="utf-8",
        )
        (fuel / "skip.md").write_text("---\ntype: other\ncost: 1\n---\n", encoding="utf-8")
        # Marker file we must never write to — mtime/content stay intact.
        self.guard = fuel / "2026-09-11.md"
        self.guard_stat = self.guard.stat()
        self.guard_bytes = self.guard.read_bytes()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_load_entries_sorted_and_filters(self) -> None:
        entries = load_fuel_entries(self.root)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].date, date(2026, 9, 11))
        self.assertEqual(entries[0].station, "Роснефть")
        self.assertEqual(entries[0].cost, 2996.0)

    def test_compute_does_not_modify_notes(self) -> None:
        payload = compute_car_fuel_board(self.root)
        self.assertEqual(payload["board"]["id"], BOARD_ID)
        self.assertEqual(self.guard.read_bytes(), self.guard_bytes)
        self.assertEqual(self.guard.stat().st_mtime_ns, self.guard_stat.st_mtime_ns)
        self.assertEqual(self.guard.stat().st_size, self.guard_stat.st_size)

    def test_document_metrics_and_rows(self) -> None:
        entries = [
            FuelEntry(
                date=date(2026, 9, 11),
                cost=1000,
                liters=10,
                station="A",
                fuel_type="95",
                path="a.md",
            ),
            FuelEntry(
                date=date(2026, 8, 1),
                cost=500,
                liters=5,
                station="B",
                fuel_type="95",
                path="b.md",
            ),
        ]
        doc = build_car_fuel_document(entries, today=date(2026, 9, 15), recent_limit=5)
        screen = doc["screen"]
        flat: list[str] = []

        def walk(node: dict) -> None:
            flat.append(node["type"])
            for child in node.get("children") or []:
                walk(child)

        walk(screen)
        self.assertIn("metric", flat)
        self.assertIn("table", flat)
        table = next(n for n in screen["children"] if n.get("type") == "table")
        self.assertEqual(len(table["rows"]), 2)

    def test_missing_folder_empty_board(self) -> None:
        empty = Path(tempfile.mkdtemp())
        try:
            payload = compute_car_fuel_board(empty)
            self.assertEqual(payload["board"]["id"], BOARD_ID)
            metrics = payload["board"]["list_cell"]["metrics"]
            self.assertEqual(metrics[0]["value"], "0 ₽")
        finally:
            # cleanup empty dir only — no vault notes involved
            empty.rmdir()


class CarFuelCatalogIntegrationTests(unittest.TestCase):
    def test_catalog_includes_live_board(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        fuel = root / "Документы" / "Тачки" / "Соляра" / "Расходы" / "Топливо"
        fuel.mkdir(parents=True)
        (fuel / "one.md").write_text(
            "---\ntype: fuel\ndate: 2026-09-01\ncost: 100\nliters: 1\n---\n",
            encoding="utf-8",
        )
        with mock.patch("kb_app_api.boards_catalog.config") as cfg:
            cfg.LOCAL_KB_PATH = root
            from kb_app_api.boards_catalog import get_board_detail, list_boards

            boards = list_boards()
            ids = [b["id"] for b in boards]
            self.assertIn(BOARD_ID, ids)
            self.assertEqual(ids[0], BOARD_ID)
            detail = get_board_detail(BOARD_ID)
            assert detail is not None
            self.assertEqual(detail["board"]["id"], BOARD_ID)
            self.assertEqual(detail["document"]["schema_version"], 1)
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
