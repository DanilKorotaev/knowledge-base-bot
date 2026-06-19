"""Tests for cursor-agent stream-json NDJSON parser."""
from __future__ import annotations

import unittest

from services.cursor_stream_parser import (
    StreamJsonAccumulator,
    activity_label,
    assistant_text_for_stream,
    parse_ndjson_line,
    result_text,
)

# Minimal sequence from Cursor docs (trimmed)
CURSOR_DOC_EXAMPLE_LINES = [
    '{"type":"system","subtype":"init","apiKeySource":"login","cwd":"/Users/user/project","session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff","model":"Claude 4 Sonnet","permissionMode":"default"}',
    '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Read README.md"}]},"session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"I\'ll read the README.md file"}]},"session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
    '{"type":"tool_call","subtype":"started","call_id":"toolu_1","tool_call":{"readToolCall":{"args":{"path":"README.md"}}},"session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
    '{"type":"tool_call","subtype":"completed","call_id":"toolu_1","tool_call":{"readToolCall":{"args":{"path":"README.md"},"result":{"success":{"content":"# Project"}}}},"session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
    '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Done!"}]},"session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
    '{"type":"result","subtype":"success","duration_ms":5234,"duration_api_ms":5234,"is_error":false,"result":"I\'ll read the README.md fileDone!","session_id":"c6b62c6f-7ead-4fd6-9922-e952131177ff"}',
]


class TestParseNdjsonLine(unittest.TestCase):
    def test_parses_system_init(self) -> None:
        event = parse_ndjson_line(CURSOR_DOC_EXAMPLE_LINES[0])
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["type"], "system")
        self.assertEqual(event["subtype"], "init")

    def test_ignores_empty_and_garbage(self) -> None:
        self.assertIsNone(parse_ndjson_line(""))
        self.assertIsNone(parse_ndjson_line("not json"))
        self.assertIsNone(parse_ndjson_line('{"type":"thinking"}'))


class TestActivityLabel(unittest.TestCase):
    def test_read_tool_started(self) -> None:
        event = parse_ndjson_line(CURSOR_DOC_EXAMPLE_LINES[3])
        assert event is not None
        label = activity_label(event)
        self.assertIsNotNone(label)
        assert label is not None
        self.assertIn("README.md", label)

    def test_system_init(self) -> None:
        event = parse_ndjson_line(CURSOR_DOC_EXAMPLE_LINES[0])
        assert event is not None
        label = activity_label(event)
        self.assertIsNotNone(label)
        assert label is not None
        self.assertIn("Claude", label)


class TestAssistantPartialFilter(unittest.TestCase):
    def test_full_segment_without_partial(self) -> None:
        event = parse_ndjson_line(CURSOR_DOC_EXAMPLE_LINES[2])
        assert event is not None
        text = assistant_text_for_stream(event, stream_partial=False)
        self.assertEqual(text, "I'll read the README.md file")

    def test_skip_buffered_flush_before_tool(self) -> None:
        line = (
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"dup"}]},'
            '"timestamp_ms":1,"model_call_id":"mc1","session_id":"x"}'
        )
        event = parse_ndjson_line(line)
        assert event is not None
        self.assertIsNone(assistant_text_for_stream(event, stream_partial=True))

    def test_accepts_streaming_delta(self) -> None:
        line = (
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Hi"}]},'
            '"timestamp_ms":1,"session_id":"x"}'
        )
        event = parse_ndjson_line(line)
        assert event is not None
        self.assertEqual(assistant_text_for_stream(event, stream_partial=True), "Hi")


class TestStreamJsonAccumulator(unittest.TestCase):
    def test_doc_sequence_prefers_result(self) -> None:
        acc = StreamJsonAccumulator(stream_partial=False)
        activities: list[str] = []
        chunks: list[str] = []
        for line in CURSOR_DOC_EXAMPLE_LINES:
            event = parse_ndjson_line(line)
            assert event is not None
            chunk, activity = acc.consume(event)
            if activity:
                activities.append(activity)
            if chunk:
                chunks.append(chunk)
        self.assertTrue(any("README" in a for a in activities))
        self.assertEqual(chunks[0], "I'll read the README.md file")
        final = acc.final_response()
        self.assertEqual(final, result_text(parse_ndjson_line(CURSOR_DOC_EXAMPLE_LINES[-1]) or {}))


if __name__ == "__main__":
    unittest.main()
