"""Read/write structured_ui JSON stored on messages rows."""

from __future__ import annotations

import json
from typing import Any


def parse_structured_ui(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return json.loads(text)
    return None


def structured_ui_by_message_ids(messages: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for message in messages:
        document = parse_structured_ui(message.get("structured_ui"))
        if document is not None:
            out[int(message["id"])] = document
    return out


def encode_structured_ui(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))
