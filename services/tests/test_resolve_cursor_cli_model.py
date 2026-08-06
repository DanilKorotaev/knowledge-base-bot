"""Unit tests for resolve_cursor_cli_model."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services.cursor_cli_service import resolve_cursor_cli_model


class TestResolveCursorCliModel(unittest.TestCase):
    def test_empty_and_auto_map_to_auto(self) -> None:
        self.assertEqual(resolve_cursor_cli_model(None), "auto")
        self.assertEqual(resolve_cursor_cli_model(""), "auto")
        self.assertEqual(resolve_cursor_cli_model("auto"), "auto")
        self.assertEqual(resolve_cursor_cli_model("Auto"), "auto")

    def test_legacy_default_maps_to_auto(self) -> None:
        self.assertEqual(resolve_cursor_cli_model("default"), "auto")
        self.assertEqual(resolve_cursor_cli_model("DEFAULT"), "auto")

    def test_explicit_model_passthrough(self) -> None:
        self.assertEqual(resolve_cursor_cli_model("composer-2.5"), "composer-2.5")
        self.assertEqual(resolve_cursor_cli_model("gpt-5.2"), "gpt-5.2")


if __name__ == "__main__":
    unittest.main()
