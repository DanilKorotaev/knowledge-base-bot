"""Bake submitted form values into a Structured UI screen document."""

from __future__ import annotations

import copy
from typing import Any

from kb_app_api.structured_ui.validate import FORM_FIELD_TYPES


def document_has_form_fields(document: dict[str, Any]) -> bool:
    screen = document.get("screen")
    if not isinstance(screen, dict):
        return False

    def walk(node: dict[str, Any]) -> bool:
        if node.get("type") in FORM_FIELD_TYPES:
            return True
        children = node.get("children")
        if not isinstance(children, list):
            return False
        return any(isinstance(child, dict) and walk(child) for child in children)

    return walk(screen)


def apply_values_to_document(
    document: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any]:
    """Return a deep copy of ``document`` with form field ``value``s from ``values``."""
    if not values:
        return document

    updated = copy.deepcopy(document)

    def walk(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        node_type = node.get("type")
        if (
            isinstance(node_id, str)
            and node_type in FORM_FIELD_TYPES
            and node_id in values
        ):
            node["value"] = values[node_id]
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    walk(child)

    screen = updated.get("screen")
    if isinstance(screen, dict):
        walk(screen)
    return updated


def latest_form_message(
    messages: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Newest assistant message whose structured_ui contains form fields."""
    from kb_app_api.structured_ui.persistence import parse_structured_ui

    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        document = parse_structured_ui(message.get("structured_ui"))
        if document is None:
            continue
        if document_has_form_fields(document):
            return message, document
    return None
