"""Optionally attach structured_ui to a normal chat assistant reply."""

from __future__ import annotations

import json
import logging
from typing import Any

from config import config
from kb_app_api.structured_ui.response_parse import StructuredUIAgentParseError, parse_agent_ui_event_payload
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_screen_document

logger = logging.getLogger(__name__)

_PROMPT = """You decide whether the Knowledge Base iOS chat reply should include an interactive Structured UI panel.

## Assistant reply (already shown / streaming to the user)

{assistant_reply}

## Recent session context

{session_context}

## Output

Return **only** one JSON object (no markdown fences):

{{"screen": null}}

or

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

## When to attach a screen

- Attach when a short choice would help: pick priority, confirm next step, multi-option checklist, yes/no fork.
- Prefer 1–4 `button`s or a small form (`checkbox` / `radio_group` / `select` / `text_field` + submit button).
- Match the user's language (RU/EN from context).
- Do **not** attach meta “Welcome to Structured UI / test MVP” screens.
- Do **not** invent `download_url` paths (`/api/attachments/...`, `guide.pdf`) — use real attachment paths from context or public `https` URLs in `url` / `download_url`.
- Do **not** attach a screen when the reply is already a complete answer with nothing to choose.
- Do **not** attach when the reply is an error or empty.

Schema v1 nodes only: vstack, text, button (+ optional submit), checkbox, radio_group, select, text_field, image (url and/or download_url), link (url), file (download_url), divider.
"""


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
    if not text or text.startswith("❌"):
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
        # Reuse ui-event parser shape, or accept {"screen": null|doc}
        stripped = raw.strip()
        if "```" in stripped:
            # fall through to parse_agent which handles fences for full ui-event payloads
            pass
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
        # Full document: {schema_version, screen}
        if "schema_version" in payload and "screen" in payload:
            if payload.get("screen") is None:
                return None
            return validate_screen_document(payload)
        # Wrapper from ui-event style: {screen: document} or {screen: null}
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
