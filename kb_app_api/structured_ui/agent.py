"""Structured UI via lightweight LLM prompt (Cursor CLI run_simple_prompt)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import config
from kb_app_api.structured_ui.mock_flow import MockUIEventResult, apply_mock_ui_event
from kb_app_api.structured_ui.response_parse import StructuredUIAgentParseError, parse_agent_ui_event_payload
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_screen_document

logger = logging.getLogger(__name__)

_prompt_cache: str | None = None


def _load_agent_prompt_template() -> str:
    global _prompt_cache
    if _prompt_cache is not None:
        return _prompt_cache

    custom = getattr(config, "STRUCTURED_UI_AGENT_PROMPT_PATH", None)
    project_root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []
    if custom:
        path = Path(custom)
        candidates.append(path if path.is_absolute() else project_root / path)
    candidates.append(project_root / "agent" / "structured_ui_agent_prompt.md")

    for path in candidates:
        if path.is_file():
            _prompt_cache = path.read_text(encoding="utf-8")
            logger.info("Structured UI agent prompt loaded from %s", path)
            return _prompt_cache

    logger.warning("Structured UI agent prompt file missing; using built-in template")
    _prompt_cache = (
        "Return JSON only: assistant_content, user_content (or null), screen (schema_version 1).\n"
        "action_id={action_id}, component_id={component_id}\n"
        "{session_context}"
    )
    return _prompt_cache


def _format_session_context(messages: list[dict[str, Any]], *, max_messages: int = 12) -> str:
    if not messages:
        return "No prior messages in this session."
    tail = messages[-max_messages:]
    lines: list[str] = []
    for message in tail:
        role = str(message.get("role", "?"))
        content = str(message.get("content", "")).strip().replace("\n", " ")
        if len(content) > 240:
            content = content[:240] + "…"
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def _build_agent_prompt(
    *,
    action_id: str,
    component_id: str,
    session_messages: list[dict[str, Any]],
) -> str:
    template = _load_agent_prompt_template()
    session_context = _format_session_context(session_messages)
    return (
        template.replace("{action_id}", action_id)
        .replace("{component_id}", component_id)
        .replace("{session_context}", session_context)
    )


async def _resolve_via_agent(
    *,
    action_id: str,
    component_id: str,
    session_messages: list[dict[str, Any]],
) -> MockUIEventResult:
    from services.cursor_cli_service import CursorCLIService

    prompt = _build_agent_prompt(
        action_id=action_id,
        component_id=component_id,
        session_messages=session_messages,
    )
    cursor = CursorCLIService()
    model = config.STRUCTURED_UI_AGENT_MODEL or config.TRANSCRIPTION_POLISH_MODEL
    raw = await cursor.run_simple_prompt(
        prompt,
        model=model,
        timeout=config.STRUCTURED_UI_AGENT_TIMEOUT,
    )
    if not raw or not raw.strip():
        raise StructuredUIAgentParseError("empty LLM response")

    payload = parse_agent_ui_event_payload(raw)
    document = validate_screen_document(payload["screen"])
    return MockUIEventResult(
        screen=document,
        user_content=payload["user_content"],
        assistant_content=payload["assistant_content"],
    )


async def resolve_ui_event(
    *,
    session_id: int,
    action_id: str,
    component_id: str,
    session_messages: list[dict[str, Any]],
) -> MockUIEventResult:
    """
    Resolve a UI event to the next screen.

    Uses LLM when STRUCTURED_UI_AGENT_ENABLED=true; falls back to mock FSM on failure
    when STRUCTURED_UI_AGENT_MOCK_FALLBACK=true.
    """
    action = action_id.strip()
    component = component_id.strip()

    if not config.STRUCTURED_UI_AGENT_ENABLED:
        return apply_mock_ui_event(action_id=action, component_id=component)

    try:
        return await _resolve_via_agent(
            action_id=action,
            component_id=component,
            session_messages=session_messages,
        )
    except (StructuredUIAgentParseError, StructuredUIValidationError, KeyError) as exc:
        logger.warning(
            "Structured UI agent failed (session_id=%s action_id=%s): %s",
            session_id,
            action,
            exc,
        )
        if config.STRUCTURED_UI_AGENT_MOCK_FALLBACK:
            return apply_mock_ui_event(action_id=action, component_id=component)
        raise
    except Exception as exc:
        logger.error(
            "Structured UI agent error (session_id=%s action_id=%s): %s",
            session_id,
            action,
            exc,
            exc_info=True,
        )
        if config.STRUCTURED_UI_AGENT_MOCK_FALLBACK:
            return apply_mock_ui_event(action_id=action, component_id=component)
        raise
