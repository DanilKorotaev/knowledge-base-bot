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
                {"type": "button", "id": "btn_form", "label": "Open form", "action_id": "open_form"},
                {
                    "type": "button",
                    "id": "btn_gallery",
                    "label": "Node gallery",
                    "action_id": "open_gallery",
                },
            ],
        }
    )


def _load_fixture(name: str) -> dict[str, Any]:
    import json
    from pathlib import Path

    fixture = Path(__file__).resolve().parent / "fixtures" / name
    doc = json.loads(fixture.read_text(encoding="utf-8"))
    return validate_screen_document(doc)


def _gallery_screen() -> dict[str, Any]:
    return _load_fixture("nodes_gallery_v1.json")


def _form_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Preferences"},
                {
                    "type": "checkbox",
                    "id": "notify",
                    "label": "Notify me",
                    "value": True,
                },
                {
                    "type": "radio_group",
                    "id": "theme",
                    "label": "Theme",
                    "value": "system",
                    "options": [
                        {"id": "system", "label": "System"},
                        {"id": "light", "label": "Light"},
                        {"id": "dark", "label": "Dark"},
                    ],
                },
                {
                    "type": "select",
                    "id": "topics",
                    "label": "Topics",
                    "multi": True,
                    "value": ["ios"],
                    "options": [
                        {"id": "ios", "label": "iOS"},
                        {"id": "bot", "label": "Bot"},
                        {"id": "infra", "label": "Infra"},
                    ],
                },
                {
                    "type": "text_field",
                    "id": "note",
                    "label": "Note",
                    "placeholder": "Optional note",
                    "max_length": 120,
                    "value": "",
                },
                {
                    "type": "button",
                    "id": "btn_submit",
                    "label": "Submit",
                    "action_id": "submit_form",
                    "submit": True,
                },
            ],
        }
    )


def _form_summary(values: dict[str, Any] | None) -> str:
    if not values:
        return "[UI] submit"
    parts: list[str] = []
    for key in sorted(values.keys()):
        value = values[key]
        if isinstance(value, bool):
            parts.append(f"{key}={'true' if value else 'false'}")
        elif isinstance(value, list):
            parts.append(f"{key}=[{','.join(str(item) for item in value)}]")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}={value}")
        else:
            text = str(value).strip()
            if text:
                parts.append(f"{key}={text}")
    return "[UI] " + "; ".join(parts) if parts else "[UI] submit"


def _form_submitted_screen(summary: str) -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Submitted"},
                {"type": "text", "id": "body", "text": summary[:4000]},
                {"type": "button", "id": "btn_done", "label": "Done", "action_id": "done"},
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


def _dismissed_screen() -> dict[str, Any]:
    return _document(
        {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Interactive UI off"},
                {
                    "type": "text",
                    "id": "body",
                    "text": "Mode turned off. You can continue in the chat.",
                },
            ],
        }
    )


def apply_mock_ui_event(
    *,
    action_id: str,
    component_id: str,
    values: dict[str, Any] | None = None,
) -> MockUIEventResult:
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

    if action == "open_form":
        return MockUIEventResult(
            screen=_form_screen(),
            user_content="[UI] Open form",
            assistant_content="Fill the form, then submit.",
        )

    if action == "open_gallery":
        return MockUIEventResult(
            screen=_gallery_screen(),
            user_content="[UI] Node gallery",
            assistant_content="Полный тест всех нод Structured UI v1.",
        )

    if action == "gallery_confirm_delete":
        return MockUIEventResult(
            screen=_document(
                {
                    "type": "vstack",
                    "id": "root",
                    "children": [
                        {"type": "text", "id": "title", "text": "Confirm OK"},
                        {
                            "type": "text",
                            "id": "body",
                            "text": "Confirm сработал. Можно отправить форму или вернуться.",
                        },
                        {
                            "type": "button",
                            "id": "btn_back",
                            "label": "Назад в gallery",
                            "action_id": "open_gallery",
                        },
                    ],
                }
            ),
            user_content="[UI] Удалить черновик",
            assistant_content="Destructive confirm accepted.",
        )

    if action == "submit_gallery":
        summary = _form_summary(values)
        return MockUIEventResult(
            screen=_form_submitted_screen(summary),
            user_content=summary,
            assistant_content="Gallery form received.",
        )

    if action == "submit_form":
        summary = _form_summary(values)
        return MockUIEventResult(
            screen=_form_submitted_screen(summary),
            user_content=summary,
            assistant_content="Form received.",
        )

    if action == "done":
        return MockUIEventResult(
            screen=_finished_screen(),
            user_content="[UI] Done",
            assistant_content="Flow finished.",
        )

    if action == "dismiss":
        return MockUIEventResult(
            screen=_dismissed_screen(),
            user_content=None,
            assistant_content="Interactive UI closed.",
        )

    raise KeyError(action)
