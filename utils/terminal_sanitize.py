"""Strip ANSI / terminal control sequences leaked from Cursor CLI PTY output."""
from __future__ import annotations

import re

# CSI sequences (e.g. \x1b[?25h show cursor) and other common ESC codes.
_ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_terminal_escape_sequences(text: str) -> str:
    if not text:
        return text
    return _ANSI_ESCAPE_RE.sub("", text).rstrip()
