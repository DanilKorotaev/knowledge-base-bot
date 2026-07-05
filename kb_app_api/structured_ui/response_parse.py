"""Parse structured UI agent JSON from raw LLM text."""

from __future__ import annotations

import json
import re
from typing import Any


class StructuredUIAgentParseError(ValueError):
    pass


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise StructuredUIAgentParseError("empty agent response")

    fence = _FENCE_RE.search(stripped)
    if fence:
        stripped = fence.group(1).strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start < 0:
        raise StructuredUIAgentParseError("no JSON object in agent response")

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                chunk = stripped[start : index + 1]
                try:
                    parsed = json.loads(chunk)
                except json.JSONDecodeError as exc:
                    raise StructuredUIAgentParseError("invalid JSON in agent response") from exc
                if not isinstance(parsed, dict):
                    raise StructuredUIAgentParseError("agent JSON root must be an object")
                return parsed

    raise StructuredUIAgentParseError("unterminated JSON object in agent response")


def parse_agent_ui_event_payload(raw: str) -> dict[str, Any]:
    """Return dict with assistant_content, user_content, screen (full document)."""
    root = _extract_json_object(raw)

    screen = root.get("screen")
    if not isinstance(screen, dict):
        raise StructuredUIAgentParseError("missing screen object")

    assistant_content = root.get("assistant_content")
    if not isinstance(assistant_content, str) or not assistant_content.strip():
        raise StructuredUIAgentParseError("missing assistant_content")

    user_content = root.get("user_content")
    if user_content is not None and not isinstance(user_content, str):
        raise StructuredUIAgentParseError("user_content must be string or null")

    return {
        "assistant_content": assistant_content.strip(),
        "user_content": user_content.strip() if isinstance(user_content, str) and user_content.strip() else None,
        "screen": screen,
    }
