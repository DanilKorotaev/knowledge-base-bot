"""Optionally attach structured_ui to a normal chat assistant reply."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import config
from kb_app_api.structured_ui.response_parse import StructuredUIAgentParseError, parse_agent_ui_event_payload
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_screen_document

logger = logging.getLogger(__name__)

_PROMPT = """You decide whether the Knowledge Base iOS chat reply should include an interactive Structured UI panel.

The user has **Interactive UI enabled** — prefer buttons/forms over asking them to type a choice in chat.

## Assistant reply (already shown / streaming to the user)

{assistant_reply}

## Recent session context

{session_context}

## Output

Return **only** one JSON object (no markdown fences):

{{"screen": null}}

or a full document:

{{
  "screen": {{
    "schema_version": 1,
    "screen": {{
      "type": "vstack",
      "id": "root",
      "children": []
    }}
  }}
}}

## When to attach a screen (important)

- **Attach** when the reply invites a decision: pick priority, yes/no, confirm next step, choose among options, set date/time, rate on a scale, or fill a short form — **even if options are already listed in the text**. Mirror options as short `button` labels or a small form.
- **Attach** when the reply ends with a question or «что выберем / как поступим / какой вариант».
- Prefer 2–6 nodes: short `text` or `callout` + `button`s, or `date`/`time`/`slider`/`stepper` + submit `button`.
- Button labels: **≤ 4 words** each. Long explanations go in `text` / `callout` / `markdown`, not button labels.
- Match the user's language (RU/EN from context).
- **Do not attach** for pure statements, finished explanations with no decision, errors, or greetings.
- **Do not** build meta/catalog screens («P2-блоки», «покрытие схемы», «выберите что проверить», Structured UI plumbing).
- **Do not** invent `download_url` paths — use real attachment paths from context or public `https` in `url` / `download_url`.
- For public demos use known-good URLs: image `https://placehold.co/360x200/png?text=KB+Image`, file `https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf`. Avoid `raw.githubusercontent.com` (often 404).

## Schema v1 nodes

vstack, hstack, text, markdown, button, confirm, checkbox, radio_group, select, text_field,
slider, stepper, date, time, image, link, file, callout, spacer, progress, divider.

Forms: local draft until `button` with `"submit": true` sends `values` (bool / string / string[] / number).
"""

_CHOICE_HINT_RE = re.compile(
    r"(?:\?|"
    r"выбер|выбери|выбрать|какой|какая|какое|какую|что\s+бер|что\s+выб|"
    r"which|pick|choose|decide|confirm|подтверд|"
    r"да\s+или\s+нет|yes\s+or\s+no|"
    r"приоритет|вариант|option|alternativ)",
    re.IGNORECASE,
)


def reply_likely_needs_ui(assistant_reply: str) -> bool:
    """Cheap gate: skip LLM when the reply clearly needs no user choice."""
    text = (assistant_reply or "").strip()
    if not text or text.startswith("❌"):
        return False
    if _CHOICE_HINT_RE.search(text):
        return True
    # Short replies without a question rarely need a panel.
    if len(text) < 80 and "?" not in text:
        return False
    return "?" in text


def _format_session_context(messages: list[dict[str, Any]], *, max_messages: int = 10) -> str:
    if not messages:
        return "No prior messages."
    lines: list[str] = []
    for message in messages[-max_messages:]:
        role = str(message.get("role", "?"))
        content = str(message.get("content", "")).strip().replace("\n", " ")
        if len(content) > 220:
            content = content[:220] + "…"
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


async def suggest_structured_ui_for_reply(
    *,
    assistant_reply: str,
    session_messages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Lightweight second prompt. Returns a validated screen document or None.
    Failures are soft (log + None) so chat replies never break.
    """
    if not getattr(config, "STRUCTURED_UI_IN_REPLIES_ENABLED", False):
        return None
    text = (assistant_reply or "").strip()
    if not reply_likely_needs_ui(text):
        return None

    from services.cursor_cli_service import CursorCLIService

    prompt = _PROMPT.format(
        assistant_reply=text[:6000],
        session_context=_format_session_context(session_messages),
    )
    cursor = CursorCLIService()
    model = config.STRUCTURED_UI_AGENT_MODEL or config.TRANSCRIPTION_POLISH_MODEL
    timeout = int(getattr(config, "STRUCTURED_UI_REPLY_SUGGEST_TIMEOUT", 45) or 45)
    try:
        raw = await cursor.run_simple_prompt(prompt, model=model, timeout=timeout)
    except Exception as exc:
        logger.warning("Structured UI reply suggest prompt failed: %s", exc)
        return None

    if not raw or not raw.strip():
        return None

    try:
        stripped = raw.strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            payload = parse_agent_ui_event_payload(raw)
            screen = payload.get("screen")
            if not screen:
                return None
            return validate_screen_document(screen)

        if not isinstance(payload, dict):
            return None
        if "schema_version" in payload and "screen" in payload:
            if payload.get("screen") is None:
                return None
            return validate_screen_document(payload)
        screen = payload.get("screen")
        if screen is None:
            return None
        if isinstance(screen, dict) and "schema_version" in screen:
            return validate_screen_document(screen)
        return None
    except (StructuredUIAgentParseError, StructuredUIValidationError, json.JSONDecodeError, KeyError) as exc:
        logger.info("Structured UI reply suggest skipped (parse/validate): %s", exc)
        return None


async def attach_structured_ui_if_suggested(
    *,
    db: Any,
    message_id: int,
    assistant_reply: str,
    session_messages: list[dict[str, Any]],
) -> bool:
    document = await suggest_structured_ui_for_reply(
        assistant_reply=assistant_reply,
        session_messages=session_messages,
    )
    if not document:
        return False
    await db.set_message_structured_ui(int(message_id), document)
    logger.info("Attached structured_ui to assistant message_id=%s", message_id)
    return True
