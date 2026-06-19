"""
Parse cursor-agent NDJSON (--output-format stream-json).

See: https://cursor.com/docs/cli/reference/output-format
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

KNOWN_EVENT_TYPES = frozenset({"system", "user", "assistant", "tool_call", "result"})

_TOOL_LABELS: dict[str, str] = {
    "readToolCall": "Читаю файл",
    "writeToolCall": "Пишу файл",
    "editToolCall": "Редактирую файл",
    "deleteToolCall": "Удаляю файл",
    "shellToolCall": "Выполняю команду",
    "grepToolCall": "Ищу в проекте",
    "lsToolCall": "Просматриваю каталог",
    "globToolCall": "Ищу файлы",
    "todoToolCall": "Обновляю задачи",
}


def parse_ndjson_line(line: str) -> Optional[dict[str, Any]]:
    """Parse one NDJSON line; return None for empty or invalid JSON."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        logger.debug("cursor_stream: invalid JSON line: %s", stripped[:200])
        return None
    if not isinstance(data, dict):
        return None
    event_type = data.get("type")
    if not isinstance(event_type, str) or event_type not in KNOWN_EVENT_TYPES:
        logger.debug("cursor_stream: unknown event type: %s", event_type)
        return None
    return data


def _assistant_message_text(event: dict[str, Any]) -> str:
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "".join(parts)


def _tool_kind_and_args(tool_call: dict[str, Any]) -> tuple[Optional[str], dict[str, Any]]:
    for kind in _TOOL_LABELS:
        payload = tool_call.get(kind)
        if isinstance(payload, dict):
            args = payload.get("args")
            return kind, args if isinstance(args, dict) else {}
    fn = tool_call.get("function")
    if isinstance(fn, dict):
        name = fn.get("name")
        if isinstance(name, str):
            return name, {}
    return None, {}


def _shorten(text: str, limit: int = 72) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[: limit - 1] + "…"


def activity_label(event: dict[str, Any]) -> Optional[str]:
    """Human-readable progress line for tool_call / system init."""
    event_type = event.get("type")
    if event_type == "system" and event.get("subtype") == "init":
        model = event.get("model")
        if isinstance(model, str) and model.strip():
            return f"Подключаюсь ({model.strip()})"
        return "Подключаюсь к агенту"

    if event_type != "tool_call" or event.get("subtype") != "started":
        return None

    tool_call = event.get("tool_call")
    if not isinstance(tool_call, dict):
        return "Выполняю инструмент"

    kind, args = _tool_kind_and_args(tool_call)
    if kind == "readToolCall":
        path = args.get("path")
        if isinstance(path, str) and path:
            return f"Читаю {_shorten(path, 56)}"
        return _TOOL_LABELS[kind]
    if kind in ("writeToolCall", "editToolCall", "deleteToolCall"):
        path = args.get("path")
        if isinstance(path, str) and path:
            verb = _TOOL_LABELS.get(kind, "Работаю с файлом")
            return f"{verb}: {_shorten(path, 48)}"
        return _TOOL_LABELS.get(kind, "Работаю с файлом")
    if kind == "shellToolCall":
        command = args.get("command") or args.get("cmd")
        if isinstance(command, str) and command.strip():
            return f"Выполняю: {_shorten(command)}"
        return _TOOL_LABELS[kind]
    if kind in _TOOL_LABELS:
        return _TOOL_LABELS[kind]
    if kind:
        return f"Инструмент: {kind}"
    return "Выполняю инструмент"


def assistant_text_for_stream(
    event: dict[str, Any],
    *,
    stream_partial: bool,
) -> Optional[str]:
    """
    Text to forward to on_chunk from an assistant event.

    Without --stream-partial-output each assistant line is a full segment.
    With partial output, only streaming deltas (timestamp_ms, no model_call_id).
    """
    if event.get("type") != "assistant":
        return None
    text = _assistant_message_text(event)
    if not text:
        return None
    if not stream_partial:
        return text
    if event.get("model_call_id"):
        return None
    if event.get("timestamp_ms") is None:
        return None
    return text


def result_text(event: dict[str, Any]) -> Optional[str]:
    if event.get("type") != "result":
        return None
    if event.get("is_error") is True:
        return None
    raw = event.get("result")
    if isinstance(raw, str):
        return raw
    return None


@dataclass
class StreamJsonAccumulator:
    """Collect canonical response and fallback segments from NDJSON events."""

    stream_partial: bool = False
    result_text_value: Optional[str] = None
    assistant_segments: list[str] = field(default_factory=list)

    def consume(self, event: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """
        Process one event.

        Returns:
            (assistant_chunk_for_stream, activity_label) — either may be None.
        """
        activity = activity_label(event)

        final = result_text(event)
        if final is not None:
            self.result_text_value = final

        chunk = assistant_text_for_stream(event, stream_partial=self.stream_partial)
        if chunk:
            self.assistant_segments.append(chunk)

        return chunk, activity

    def final_response(self) -> str:
        if self.result_text_value is not None:
            return self.result_text_value
        if self.assistant_segments:
            if self.stream_partial:
                return "".join(self.assistant_segments)
            return "".join(self.assistant_segments)
        return ""
