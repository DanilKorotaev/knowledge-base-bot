"""Structured UI (backend-driven screen JSON) — MVP v1."""

from kb_app_api.structured_ui.mock_flow import apply_mock_ui_event
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_screen_document

__all__ = [
    "StructuredUIValidationError",
    "apply_mock_ui_event",
    "validate_screen_document",
]
