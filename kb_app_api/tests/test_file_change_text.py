"""Tests for binary / oversized file_change text sanitization."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from utils.file_helpers import (
    is_binary_kb_path,
    looks_like_binary_blob,
    read_text_for_file_change,
    sanitize_file_change_text,
)


class TestFileChangeText(unittest.TestCase):
    def test_is_binary_kb_path_images(self) -> None:
        self.assertTrue(is_binary_kb_path("Питание/_raw/x.jpg"))
        self.assertTrue(is_binary_kb_path("a/b.PNG"))
        self.assertFalse(is_binary_kb_path("notes/x.md"))
        self.assertFalse(is_binary_kb_path("Boards/lib/nutrition_board.py"))

    def test_sanitize_drops_binary_path_and_blob(self) -> None:
        self.assertIsNone(sanitize_file_change_text("a.jpg", "pretend"))
        self.assertIsNone(sanitize_file_change_text("a.md", "\x00binary"))
        self.assertEqual(sanitize_file_change_text("a.md", "hello"), "hello")

    def test_looks_like_binary_blob(self) -> None:
        self.assertFalse(looks_like_binary_blob("normal text " * 50))
        self.assertTrue(looks_like_binary_blob("\x00" + ("x" * 600)))

    def test_read_text_for_file_change_skips_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            jpeg = Path(tmp) / "label.jpg"
            jpeg.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
            self.assertIsNone(read_text_for_file_change(jpeg))
            md = Path(tmp) / "note.md"
            md.write_text("# hi\n", encoding="utf-8")
            self.assertEqual(read_text_for_file_change(md), "# hi\n")


if __name__ == "__main__":
    unittest.main()
