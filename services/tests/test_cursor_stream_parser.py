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
        # Second assistant turn is glued by Cursor in ``result``; we heal it.
        self.assertTrue(chunks[1].startswith("\n\n") or chunks[1] == "Done!")
        final = acc.final_response()
        self.assertIn("I'll read the README.md file", final)
        self.assertIn("Done!", final)
        self.assertNotIn("fileDone", final)

    def test_heals_heading_stuck_to_previous_sentence(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = "Сначала посмотрю поля.B QueryJob уже есть.### Итог\nТекст"
        healed = heal_glued_assistant_text(raw)
        self.assertIn("есть.\n\n### Итог", healed)
        self.assertIn("поля.\n\nB QueryJob", healed)

    def test_heal_does_not_split_atx_heading_hashes(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = "Сделано обе фичи.\n\n### Архив сессий\nКак у бордов.\n\n### Автоназвание\nТекст."
        healed = heal_glued_assistant_text(raw)
        self.assertIn("### Архив сессий", healed)
        self.assertIn("### Автоназвание", healed)
        self.assertNotIn("\n#\n\n## ", healed)
        self.assertNotIn("\n#\n## ", healed)
        self.assertEqual(healed.count("###"), 2)

    def test_heal_collapses_legacy_split_atx(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = "Готово.\n\n#\n\n## Архив сессий\nТекст.\n\n#\n## Автоназвание"
        healed = heal_glued_assistant_text(raw)
        self.assertIn("### Архив сессий", healed)
        self.assertIn("### Автоназвание", healed)
        self.assertNotIn("#\n\n##", healed)

    def test_heal_preserves_bold_and_inline_code(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = (
            "**Пачка 1 (тест склейки).** Сейчас пример `делаю.Если` / "
            "`абзац.Проблема`.**Пачка 2 — смотри сюда.** Между пачками."
        )
        healed = heal_glued_assistant_text(raw)
        self.assertIn("**Пачка 1 (тест склейки).** Сейчас", healed)
        self.assertIn("`делаю.Если`", healed)
        self.assertIn("`абзац.Проблема`", healed)
        self.assertIn("`абзац.Проблема`.\n\n**Пачка 2 — смотри сюда.**", healed)
        self.assertNotIn(".*\n\n*", healed)

    def test_heal_does_not_break_plus_in_prose_or_double_backticks(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = (
            "**Склейка (по скринам + БД)**\n\n"
            "Плюс старый хилер ломал `**bold**` и резал текст внутри `` `кода` ``."
        )
        healed = heal_glued_assistant_text(raw)
        self.assertIn("**Склейка (по скринам + БД)**", healed)
        self.assertNotIn("скринам \n\n+ БД", healed)
        self.assertIn("`` `кода` ``", healed)

    def test_heal_preserves_numbered_and_bullet_lists(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = (
            "Сделано.\n\n"
            "1. **Первый пункт** — нормальный.\n"
            "2. Второй с `кодом.Внутри`.\n"
            "- bullet ok\n"
            "* star ok\n"
            "+ plus list ok\n"
            "И проза про скринам + БД без разрыва."
        )
        healed = heal_glued_assistant_text(raw)
        self.assertIn("1. **Первый пункт**", healed)
        self.assertIn("2. Второй", healed)
        self.assertIn("- bullet ok", healed)
        self.assertIn("* star ok", healed)
        self.assertIn("+ plus list ok", healed)
        self.assertIn("скринам + БД", healed)
        self.assertNotIn("\n\n1. ", healed.replace("Сделано.\n\n1. ", ""))

    def test_heal_does_not_touch_mid_word_hash_or_fence(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = "tag#name and C## style stay; only after punct.### Heading\nDone.```py\nx=1\n```"
        healed = heal_glued_assistant_text(raw)
        self.assertIn("tag#name", healed)
        self.assertIn("C## style", healed)
        self.assertIn("punct.\n\n### Heading", healed)
        self.assertIn("Done.\n\n```py", healed)

    def test_heal_fenced_code_body_untouched(self) -> None:
        from services.cursor_stream_parser import heal_glued_assistant_text

        raw = (
            "Intro.\n\n```\nfoo.Bar### not heading\n1. not list\n```\n\n"
            "Closing without punct**Bold mid** then Out.**Next para.**"
        )
        healed = heal_glued_assistant_text(raw)
        self.assertIn("foo.Bar### not heading", healed)
        self.assertIn("1. not list", healed)
        self.assertIn("punct**Bold mid**", healed)
        self.assertIn("Out.\n\n**Next para.**", healed)

    def test_separator_between_segments_for_markdown(self) -> None:
        from services.cursor_stream_parser import separator_between_segments

        self.assertEqual(
            separator_between_segments("Сначала посмотрю.", "**Сделано.**"),
            "\n\n",
        )
        self.assertEqual(separator_between_segments("Hello\n", "world"), "")
        self.assertEqual(separator_between_segments("Done.", "### Title"), "\n\n")
        self.assertEqual(separator_between_segments("Done.", "- item"), "\n\n")
        self.assertEqual(separator_between_segments("Done.", "1. item"), "\n\n")
        self.assertEqual(separator_between_segments("Done.", "```py"), "\n\n")

if __name__ == "__main__":
    unittest.main()
