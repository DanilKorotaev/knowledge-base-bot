"""Tests for terminal escape sequence sanitization."""
from __future__ import annotations

import unittest

from utils.terminal_sanitize import strip_terminal_escape_sequences


class TestTerminalSanitize(unittest.TestCase):
    def test_strips_show_cursor_sequence(self) -> None:
        raw = "Hello world.\n\u001b[?25h"
        self.assertEqual(strip_terminal_escape_sequences(raw), "Hello world.")

    def test_preserves_plain_text(self) -> None:
        text = "Line one\nLine two"
        self.assertEqual(strip_terminal_escape_sequences(text), text)


if __name__ == "__main__":
    unittest.main()
