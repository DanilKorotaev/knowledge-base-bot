"""Validate structured UI screen documents (schema_version 1)."""

from __future__ import annotations

from typing import Any

MAX_DOCUMENT_BYTES = 32_768
MAX_NODES = 50
MAX_DEPTH = 8
MAX_TEXT_LENGTH = 4_000
MAX_LABEL_LENGTH = 200
MAX_ID_LENGTH = 128
MAX_OPTIONS = 32
MAX_VALUES_KEYS = 40
SUPPORTED_SCHEMA_VERSION = 1
ALLOWED_NODE_TYPES = frozenset(
    {
        "vstack",
        "text",
        "button",
        "checkbox",
        "radio_group",
        "select",
        "text_field",
        "image",
        "link",
        "file",
        "divider",
    }
)
FORM_FIELD_TYPES = frozenset({"checkbox", "radio_group", "select", "text_field"})
MAX_URL_LENGTH = 2_000
MAX_FILE_NAME_LENGTH = 260
MAX_ALT_LENGTH = 500


class StructuredUIValidationError(ValueError):
    def __init__(self, code: str, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _require_string(value: Any, *, field: str, max_len: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StructuredUIValidationError("validation_error", f"{field} is required", detail=field)
    if len(value) > max_len:
        raise StructuredUIValidationError("validation_error", f"{field} is too long", detail=field)
    return value


def _validate_options(options: Any) -> None:
    if not isinstance(options, list) or not options:
        raise StructuredUIValidationError(
            "validation_error",
            "options must be a non-empty array",
            detail="options",
        )
    if len(options) > MAX_OPTIONS:
        raise StructuredUIValidationError("validation_error", "too many options", detail="options")
    seen: set[str] = set()
    for option in options:
        if not isinstance(option, dict):
            raise StructuredUIValidationError(
                "validation_error",
                "option must be an object",
                detail="options",
            )
        opt_id = _require_string(option.get("id"), field="options.id", max_len=MAX_ID_LENGTH)
        _require_string(option.get("label"), field="options.label", max_len=MAX_LABEL_LENGTH)
        if opt_id in seen:
            raise StructuredUIValidationError(
                "validation_error",
                f"duplicate option id: {opt_id}",
                detail="options",
            )
        seen.add(opt_id)


def _validate_http_url(raw: Any, *, field: str) -> str:
    url = _require_string(raw, field=field, max_len=MAX_URL_LENGTH)
    lowered = url.lower()
    if not (lowered.startswith("https://") or lowered.startswith("http://")):
        raise StructuredUIValidationError(
            "validation_error",
            f"{field} must be http(s) URL",
            detail=field,
        )
    rest = url.split("://", 1)[1]
    host = rest.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if not host:
        raise StructuredUIValidationError(
            "validation_error",
            f"{field} must include a host",
            detail=field,
        )
    return url


def _validate_download_path(raw: Any, *, field: str) -> str:
    path = _require_string(raw, field=field, max_len=MAX_URL_LENGTH)
    if ".." in path:
        raise StructuredUIValidationError(
            "validation_error",
            f"{field} must not contain '..'",
            detail=field,
        )
    lowered = path.lower()
    if lowered.startswith("https://") or lowered.startswith("http://"):
        _validate_http_url(path, field=field)
        return path
    if lowered.startswith("file://"):
        return path
    if path.startswith("/"):
        return path
    # Relative API path — reject other URI schemes (javascript:, data:, …)
    scheme, sep, _ = path.partition(":")
    if sep and scheme.isalpha():
        raise StructuredUIValidationError(
            "validation_error",
            f"{field} has unsupported URI scheme",
            detail=field,
        )
    return path


def _validate_value_for_type(node_type: str, value: Any) -> None:
    if value is None:
        return
    if node_type == "checkbox":
        if not isinstance(value, bool):
            raise StructuredUIValidationError(
                "validation_error",
                "checkbox value must be boolean",
                detail="value",
            )
        return
    if node_type in {"radio_group", "text_field"}:
        if not isinstance(value, str):
            raise StructuredUIValidationError(
                "validation_error",
                f"{node_type} value must be string",
                detail="value",
            )
        if len(value) > MAX_TEXT_LENGTH:
            raise StructuredUIValidationError("validation_error", "value is too long", detail="value")
        return
    if node_type == "select":
        if isinstance(value, str):
            if len(value) > MAX_ID_LENGTH:
                raise StructuredUIValidationError("validation_error", "value is too long", detail="value")
            return
        if isinstance(value, list):
            if len(value) > MAX_OPTIONS:
                raise StructuredUIValidationError("validation_error", "too many selected values", detail="value")
            for item in value:
                if not isinstance(item, str) or len(item) > MAX_ID_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "select multi value must be string ids",
                        detail="value",
                    )
            return
        raise StructuredUIValidationError(
            "validation_error",
            "select value must be string or string array",
            detail="value",
        )


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

        _require_string(node.get("id"), field="id", max_len=MAX_ID_LENGTH)

        if node_type == "text":
            text = node.get("text")
            if not isinstance(text, str):
                raise StructuredUIValidationError("validation_error", "text node requires string text", detail="text")
            if len(text) > MAX_TEXT_LENGTH:
                raise StructuredUIValidationError("validation_error", "text is too long", detail="text")
            return

        if node_type == "button":
            _require_string(node.get("label"), field="label", max_len=MAX_LABEL_LENGTH)
            _require_string(node.get("action_id"), field="action_id", max_len=MAX_ID_LENGTH)
            submit = node.get("submit")
            if submit is not None and not isinstance(submit, bool):
                raise StructuredUIValidationError(
                    "validation_error",
                    "button submit must be boolean",
                    detail="submit",
                )
            return

        if node_type == "checkbox":
            _require_string(node.get("label"), field="label", max_len=MAX_LABEL_LENGTH)
            _validate_value_for_type(node_type, node.get("value"))
            return

        if node_type in {"radio_group", "select"}:
            label = node.get("label")
            if label is not None:
                _require_string(label, field="label", max_len=MAX_LABEL_LENGTH)
            _validate_options(node.get("options"))
            multi = node.get("multi")
            if multi is not None and not isinstance(multi, bool):
                raise StructuredUIValidationError(
                    "validation_error",
                    "select multi must be boolean",
                    detail="multi",
                )
            if node_type == "radio_group" and multi is True:
                raise StructuredUIValidationError(
                    "validation_error",
                    "radio_group cannot be multi",
                    detail="multi",
                )
            _validate_value_for_type(node_type, node.get("value"))
            return

        if node_type == "text_field":
            label = node.get("label")
            if label is not None:
                _require_string(label, field="label", max_len=MAX_LABEL_LENGTH)
            placeholder = node.get("placeholder")
            if placeholder is not None:
                if not isinstance(placeholder, str) or len(placeholder) > MAX_LABEL_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "invalid placeholder",
                        detail="placeholder",
                    )
            max_length = node.get("max_length")
            if max_length is not None:
                if not isinstance(max_length, int) or max_length < 1 or max_length > MAX_TEXT_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "invalid max_length",
                        detail="max_length",
                    )
            _validate_value_for_type(node_type, node.get("value"))
            return

        if node_type == "divider":
            return

        if node_type == "link":
            _validate_http_url(node.get("url"), field="url")
            label = node.get("label")
            if label is not None:
                _require_string(label, field="label", max_len=MAX_LABEL_LENGTH)
            return

        if node_type == "image":
            url = node.get("url")
            download_url = node.get("download_url")
            if url is None and download_url is None:
                raise StructuredUIValidationError(
                    "validation_error",
                    "image requires url or download_url",
                    detail="url",
                )
            if url is not None:
                _validate_http_url(url, field="url")
            if download_url is not None:
                _validate_download_path(download_url, field="download_url")
            alt = node.get("alt")
            if alt is not None:
                if not isinstance(alt, str) or len(alt) > MAX_ALT_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "invalid alt",
                        detail="alt",
                    )
            label = node.get("label")
            if label is not None:
                _require_string(label, field="label", max_len=MAX_LABEL_LENGTH)
            content_mode = node.get("content_mode")
            if content_mode is not None and content_mode not in {"fit", "fill"}:
                raise StructuredUIValidationError(
                    "validation_error",
                    "content_mode must be fit or fill",
                    detail="content_mode",
                )
            return

        if node_type == "file":
            _validate_download_path(node.get("download_url"), field="download_url")
            file_name = node.get("file_name")
            if file_name is not None:
                if not isinstance(file_name, str) or not file_name.strip() or len(file_name) > MAX_FILE_NAME_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "invalid file_name",
                        detail="file_name",
                    )
            file_size = node.get("file_size")
            if file_size is not None and (not isinstance(file_size, int) or file_size < 0):
                raise StructuredUIValidationError(
                    "validation_error",
                    "invalid file_size",
                    detail="file_size",
                )
            label = node.get("label")
            if label is not None:
                _require_string(label, field="label", max_len=MAX_LABEL_LENGTH)
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


def validate_event_values(values: Any) -> dict[str, Any] | None:
    """Validate optional ui-events.values map (form submit payload)."""
    if values is None:
        return None
    if not isinstance(values, dict):
        raise StructuredUIValidationError("validation_error", "values must be an object", detail="values")
    if len(values) > MAX_VALUES_KEYS:
        raise StructuredUIValidationError("validation_error", "too many values keys", detail="values")

    cleaned: dict[str, Any] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip() or len(key) > MAX_ID_LENGTH:
            raise StructuredUIValidationError("validation_error", "invalid values key", detail="values")
        if isinstance(value, bool):
            cleaned[key] = value
            continue
        if isinstance(value, str):
            if len(value) > MAX_TEXT_LENGTH:
                raise StructuredUIValidationError("validation_error", "values string too long", detail="values")
            cleaned[key] = value
            continue
        if isinstance(value, list):
            if len(value) > MAX_OPTIONS:
                raise StructuredUIValidationError("validation_error", "values list too long", detail="values")
            items: list[str] = []
            for item in value:
                if not isinstance(item, str) or len(item) > MAX_ID_LENGTH:
                    raise StructuredUIValidationError(
                        "validation_error",
                        "values list items must be short strings",
                        detail="values",
                    )
                items.append(item)
            cleaned[key] = items
            continue
        raise StructuredUIValidationError(
            "validation_error",
            "values entries must be bool, string, or string array",
            detail="values",
        )

    validate_document_size({"values": cleaned})
    return cleaned


def validate_document_size(raw: dict[str, Any]) -> None:
    import json

    encoded = json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise StructuredUIValidationError("validation_error", "structured_ui payload is too large")
