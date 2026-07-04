"""Deterministic mock UI flow for MVP E2E (no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kb_app_api.structured_ui.validate import validate_screen_document


@dataclass(frozen=True)
class MockUIEventResult:
    screen: dict[str, Any]
    user_content: str | None
    assistant_content: str


def _document(screen: dict[str, Any]) -> dict[str, Any]:
    doc = {"schema_version": 1, "screen": screen}
    return validate_screen_document(doc)


def _welcome_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Choose an action"},
                {"type": "text", "id": "subtitle", "text": "Mock structured UI flow (MVP)."},
                {"type": "button", "id": "btn_yes", "label": "Yes", "action_id": "confirm_yes"},
                {"type": "button", "id": "btn_no", "label": "No", "action_id": "confirm_no"},
            ],
        }
    )


def _confirmed_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Confirmed"},
                {"type": "text", "id": "body", "text": "You chose Yes. Tap Done to finish."},
                {"type": "button", "id": "btn_done", "label": "Done", "action_id": "done"},
            ],
        }
    )


def _declined_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Declined"},
                {"type": "text", "id": "body", "text": "You chose No. Tap Done to finish."},
                {"type": "button", "id": "btn_done", "label": "Done", "action_id": "done"},
            ],
        }
    )


def _finished_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Finished"},
                {"type": "text", "id": "body", "text": "Mock flow complete."},
            ],
        }
    )


def apply_mock_ui_event(*, action_id: str, component_id: str) -> MockUIEventResult:
    action = action_id.strip()
    _ = component_id

    if action == "start":
        return MockUIEventResult(
            screen=_welcome_screen(),
            user_content=None,
            assistant_content="Interactive UI ready.",
        )

    if action == "confirm_yes":
        return MockUIEventResult(
            screen=_confirmed_screen(),
            user_content="[UI] Yes",
            assistant_content="You selected Yes.",
        )

    if action == "confirm_no":
        return MockUIEventResult(
            screen=_declined_screen(),
            user_content="[UI] No",
            assistant_content="You selected No.",
        )

    if action == "done":
        return MockUIEventResult(
            screen=_finished_screen(),
            user_content="[UI] Done",
            assistant_content="Flow finished.",
        )

    raise KeyError(action)
