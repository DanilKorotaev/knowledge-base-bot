"""Validate structured UI screen documents (schema_version 1)."""

from __future__ import annotations

from typing import Any

MAX_DOCUMENT_BYTES = 32_768
MAX_NODES = 50
MAX_DEPTH = 8
MAX_TEXT_LENGTH = 4_000
MAX_LABEL_LENGTH = 200
MAX_ID_LENGTH = 128
SUPPORTED_SCHEMA_VERSION = 1
ALLOWED_NODE_TYPES = frozenset({"vstack", "text", "button"})


class StructuredUIValidationError(ValueError):
    def __init__(self, code: str, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def validate_screen_document(document: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StructuredUIValidationError("validation_error", "structured_ui must be an object")

    schema_version = document.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise StructuredUIValidationError(
            "unsupported_schema_version",
            f"Unsupported schema_version: {schema_version!r}",
            detail="schema_version",
        )

    screen = document.get("screen")
    if not isinstance(screen, dict):
        raise StructuredUIValidationError("validation_error", "screen must be an object", detail="screen")

    node_count = 0

    def walk(node: dict[str, Any], depth: int) -> None:
        nonlocal node_count
        if depth > MAX_DEPTH:
            raise StructuredUIValidationError("validation_error", "screen tree is too deep", detail="screen")
        node_count += 1
        if node_count > MAX_NODES:
            raise StructuredUIValidationError("validation_error", "too many UI nodes", detail="screen")

        node_type = node.get("type")
        if node_type not in ALLOWED_NODE_TYPES:
            raise StructuredUIValidationError(
                "validation_error",
                f"Unsupported node type: {node_type!r}",
                detail="type",
            )

        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            raise StructuredUIValidationError("validation_error", "node id is required", detail="id")
        if len(node_id) > MAX_ID_LENGTH:
            raise StructuredUIValidationError("validation_error", "node id is too long", detail="id")

        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise StructuredUIValidationError("validation_error", "text node requires string text", detail="text")
            if len(text) > MAX_TEXT_LENGTH:
                raise StructuredUIValidationError("validation_error", "text is too long", detail="text")
            return

        if node_type == "button":
            label = node.get("label")
            action_id = node.get("action_id")
            if not isinstance(label, str) or not label.strip():
                raise StructuredUIValidationError("validation_error", "button requires label", detail="label")
            if len(label) > MAX_LABEL_LENGTH:
                raise StructuredUIValidationError("validation_error", "button label is too long", detail="label")
            if not isinstance(action_id, str) or not action_id.strip():
                raise StructuredUIValidationError(
                    "validation_error",
                    "button requires action_id",
                    detail="action_id",
                )
            if len(action_id) > MAX_ID_LENGTH:
                raise StructuredUIValidationError("validation_error", "action_id is too long", detail="action_id")
            return

        children = node.get("children")
        if children is None:
            return
        if not isinstance(children, list):
            raise StructuredUIValidationError("validation_error", "children must be an array", detail="children")
        for child in children:
            if not isinstance(child, dict):
                raise StructuredUIValidationError("validation_error", "child node must be an object", detail="children")
            walk(child, depth + 1)

    walk(screen, depth=1)
    return document


def validate_document_size(raw: dict[str, Any]) -> None:
    import json

    encoded = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise StructuredUIValidationError("validation_error", "structured_ui payload is too large")
