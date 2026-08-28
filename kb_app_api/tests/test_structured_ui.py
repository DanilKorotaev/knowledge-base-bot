"""Unit and HTTP tests for structured UI MVP (schema v1, mock flow, ui-events)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kb_app_api.structured_ui.mock_flow import apply_mock_ui_event
from kb_app_api.structured_ui.persistence import parse_structured_ui, structured_ui_by_message_ids
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_screen_document

_db_file: str | None = None
_kb_dir: str | None = None


def setUpModule() -> None:
    global _db_file, _kb_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_API_TOKEN"] = "structured-ui-test-bearer"
    os.environ["KB_APP_API_TELEGRAM_ID"] = "9000000009000002"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    Path(_kb_dir).mkdir(parents=True, exist_ok=True)


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


class TestStructuredUIValidation(unittest.TestCase):
    def test_valid_welcome_document(self) -> None:
        doc = apply_mock_ui_event(action_id="start", component_id="bootstrap").screen
        validated = validate_screen_document(doc)
        self.assertEqual(validated["schema_version"], 1)
        self.assertEqual(validated["screen"]["type"], "vstack")

    def test_rejects_unknown_node_type(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {"type": "carousel", "id": "root"},
        }
        with self.assertRaises(StructuredUIValidationError) as ctx:
            validate_screen_document(doc)
        self.assertEqual(ctx.exception.code, "validation_error")

    def test_rejects_unsupported_schema_version(self) -> None:
        doc = {
            "schema_version": 99,
            "screen": {"type": "vstack", "id": "root"},
        }
        with self.assertRaises(StructuredUIValidationError) as ctx:
            validate_screen_document(doc)
        self.assertEqual(ctx.exception.code, "unsupported_schema_version")

    def test_accepts_p3_nodes(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [
                    {"type": "markdown", "id": "md", "text": "**Hi**"},
                    {"type": "slider", "id": "s", "min": 0, "max": 10, "value": 4},
                    {"type": "stepper", "id": "n", "min": 1, "max": 5, "value": 2},
                    {
                        "type": "confirm",
                        "id": "c",
                        "label": "Delete",
                        "action_id": "delete",
                        "text": "Sure?",
                    },
                ],
            },
        }
        validated = validate_screen_document(doc)
        self.assertEqual(len(validated["screen"]["children"]), 4)

    def test_event_values_accepts_numbers(self) -> None:
        from kb_app_api.structured_ui.validate import validate_event_values

        cleaned = validate_event_values({"volume": 7, "qty": 2.5})
        self.assertEqual(cleaned, {"volume": 7, "qty": 2.5})

    def test_accepts_p2_layout_nodes(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [
                    {
                        "type": "callout",
                        "id": "c1",
                        "variant": "tip",
                        "text": "Remember to save.",
                    },
                    {"type": "spacer", "id": "s1", "height": 16},
                    {"type": "progress", "id": "p1", "value": 0.4, "label": "Loading"},
                    {"type": "progress", "id": "p2", "current": 1, "total": 3},
                    {"type": "date", "id": "due", "value": "2026-08-28"},
                    {"type": "time", "id": "at", "value": "09:15"},
                    {
                        "type": "hstack",
                        "id": "row",
                        "children": [
                            {"type": "button", "id": "b1", "label": "OK", "action_id": "ok"},
                        ],
                    },
                ],
            },
        }
        validated = validate_screen_document(doc)
        self.assertEqual(len(validated["screen"]["children"]), 7)

    def test_rejects_invalid_progress(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {"type": "progress", "id": "p1", "value": 1.5},
        }
        with self.assertRaises(StructuredUIValidationError):
            validate_screen_document(doc)

    def test_rejects_invalid_date_value(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {"type": "date", "id": "d1", "value": "28-08-2026"},
        }
        with self.assertRaises(StructuredUIValidationError):
            validate_screen_document(doc)

    def test_accepts_media_nodes(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [
                    {"type": "divider", "id": "d1"},
                    {
                        "type": "image",
                        "id": "img1",
                        "url": "https://example.com/a.png",
                        "alt": "Sample",
                        "content_mode": "fit",
                    },
                    {
                        "type": "link",
                        "id": "lnk1",
                        "url": "https://example.com/docs",
                        "label": "Docs",
                    },
                    {
                        "type": "file",
                        "id": "f1",
                        "download_url": "/api/attachments/1/download",
                        "file_name": "notes.pdf",
                        "file_size": 10,
                    },
                ],
            },
        }
        validated = validate_screen_document(doc)
        self.assertEqual(len(validated["screen"]["children"]), 4)

    def test_rejects_javascript_link(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {
                "type": "link",
                "id": "bad",
                "url": "javascript:alert(1)",
            },
        }
        with self.assertRaises(StructuredUIValidationError):
            validate_screen_document(doc)

    def test_rejects_image_without_source(self) -> None:
        doc = {
            "schema_version": 1,
            "screen": {"type": "image", "id": "img"},
        }
        with self.assertRaises(StructuredUIValidationError):
            validate_screen_document(doc)


class TestStructuredUIMockFlow(unittest.TestCase):
    def test_start_returns_welcome(self) -> None:
        result = apply_mock_ui_event(action_id="start", component_id="bootstrap")
        self.assertIsNone(result.user_content)
        self.assertEqual(result.assistant_content, "Interactive UI ready.")
        buttons = [
            child
            for child in result.screen["screen"].get("children", [])
            if child.get("type") == "button"
        ]
        self.assertEqual(len(buttons), 4)
        self.assertTrue(any(b.get("action_id") == "open_form" for b in buttons))
        self.assertTrue(any(b.get("action_id") == "open_gallery" for b in buttons))

    def test_gallery_screen_has_all_node_families(self) -> None:
        result = apply_mock_ui_event(action_id="open_gallery", component_id="btn_gallery")

        def collect_types(node: dict) -> list[str]:
            types = [node.get("type", "")]
            for child in node.get("children") or []:
                types.extend(collect_types(child))
            return types

        types = collect_types(result.screen["screen"])
        for expected in (
            "markdown",
            "callout",
            "hstack",
            "spacer",
            "progress",
            "image",
            "link",
            "file",
            "checkbox",
            "radio_group",
            "select",
            "text_field",
            "date",
            "time",
            "slider",
            "stepper",
            "confirm",
        ):
            self.assertIn(expected, types, msg=f"missing node type {expected}")

    def test_submit_gallery_uses_numeric_values(self) -> None:
        result = apply_mock_ui_event(
            action_id="submit_gallery",
            component_id="btn_submit",
            values={"volume": 7, "qty": 2, "theme": "dark", "note": "ok"},
        )
        self.assertIn("volume=7", result.user_content or "")
        self.assertIn("qty=2", result.user_content or "")
        self.assertIn("theme=dark", result.user_content or "")

    def test_gallery_confirm_action(self) -> None:
        result = apply_mock_ui_event(
            action_id="gallery_confirm_delete",
            component_id="btn_delete",
        )
        self.assertEqual(result.user_content, "[UI] Удалить черновик")
        self.assertEqual(result.screen["screen"]["children"][0]["text"], "Confirm OK")

    def test_submit_form_uses_values(self) -> None:
        result = apply_mock_ui_event(
            action_id="submit_form",
            component_id="btn_submit",
            values={"notify": True, "theme": "dark", "note": "hi"},
        )
        self.assertEqual(result.user_content, "[UI] note=hi; notify=true; theme=dark")
        self.assertEqual(result.screen["screen"]["children"][0]["text"], "Submitted")

    def test_dismiss_has_no_user_stub_and_no_buttons(self) -> None:
        result = apply_mock_ui_event(action_id="dismiss", component_id="toolbar_dismiss")
        self.assertIsNone(result.user_content)
        self.assertEqual(result.assistant_content, "Interactive UI closed.")
        buttons = [
            child
            for child in result.screen["screen"].get("children", [])
            if child.get("type") == "button"
        ]
        self.assertEqual(buttons, [])

        result = apply_mock_ui_event(action_id="confirm_yes", component_id="btn_yes")
        self.assertEqual(result.user_content, "[UI] Yes")

    def test_unknown_action_raises(self) -> None:
        with self.assertRaises(KeyError):
            apply_mock_ui_event(action_id="unknown", component_id="x")


class TestStructuredUIPersistence(unittest.TestCase):
    def test_structured_ui_by_message_ids_from_rows(self) -> None:
        doc = apply_mock_ui_event(action_id="start", component_id="bootstrap").screen
        by_msg = structured_ui_by_message_ids(
            [
                {"id": 1, "role": "user", "content": "hi"},
                {"id": 2, "role": "assistant", "content": "ready", "structured_ui": doc},
            ]
        )
        self.assertEqual(by_msg[2]["schema_version"], 1)

    def test_parse_structured_ui_from_json_string(self) -> None:
        doc = apply_mock_ui_event(action_id="start", component_id="bootstrap").screen
        import json

        parsed = parse_structured_ui(json.dumps(doc, ensure_ascii=False))
        self.assertEqual(parsed, doc)


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestStructuredUIEventsHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # config / db singleton may already be loaded (other test modules) — force test env
        from config import config

        config.KB_APP_API_TOKEN = os.environ["KB_APP_API_TOKEN"]
        config.KB_APP_API_TELEGRAM_ID = int(os.environ["KB_APP_API_TELEGRAM_ID"])
        config.ACCESS_MODE = "open"
        config.KB_APP_API_BYPASS_ACCESS_CHECK = True
        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])
        # Prod dotenv may enable agent — HTTP tests assert the deterministic mock FSM.
        config.STRUCTURED_UI_AGENT_ENABLED = False
        config.STRUCTURED_UI_AGENT_MOCK_FALLBACK = True

        # Reset cached DB so sqlite test DB is used instead of prod postgres from dotenv
        import utils.db_helpers as db_helpers

        db_helpers._db_instance = None  # type: ignore[attr-defined]

        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer structured-ui-test-bearer"}

    def _create_session(self) -> str:
        response = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Structured UI"},
        )
        self.assertEqual(response.status_code, 201)
        return str(response.json()["session"]["id"])

    def test_ui_events_requires_bearer(self) -> None:
        response = self.client.post(
            "/api/sessions/1/ui-events",
            json={"action_id": "start", "component_id": "bootstrap"},
        )
        self.assertEqual(response.status_code, 401)

    def test_start_flow_e2e(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/ui-events",
            headers=self.headers,
            json={
                "action_id": "start",
                "component_id": "bootstrap",
                "client_schema_version": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["screen"]["schema_version"], 1)
        self.assertIn("messages", body)
        assistant = next(m for m in body["messages"] if m["role"] == "assistant")
        self.assertEqual(assistant.get("structured_ui", {}).get("schema_version"), 1)

        listed = self.client.get(
            f"/api/sessions/{sid}/messages",
            headers=self.headers,
        )
        self.assertEqual(listed.status_code, 200)
        listed_assistant = next(m for m in listed.json()["messages"] if m["role"] == "assistant")
        self.assertIn("structured_ui", listed_assistant)

    def test_button_tap_advances_flow(self) -> None:
        sid = self._create_session()
        self.client.post(
            f"/api/sessions/{sid}/ui-events",
            headers=self.headers,
            json={"action_id": "start", "component_id": "bootstrap"},
        )
        response = self.client.post(
            f"/api/sessions/{sid}/ui-events",
            headers=self.headers,
            json={"action_id": "confirm_yes", "component_id": "btn_yes"},
        )
        self.assertEqual(response.status_code, 200)
        messages = response.json()["messages"]
        user_stub = next(m for m in messages if m["role"] == "user" and m["content"] == "[UI] Yes")
        self.assertIsNotNone(user_stub)
        self.assertEqual(
            response.json()["screen"]["screen"]["children"][0]["text"],
            "Confirmed",
        )

    def test_unknown_action_returns_400(self) -> None:
        sid = self._create_session()
        response = self.client.post(
            f"/api/sessions/{sid}/ui-events",
            headers=self.headers,
            json={"action_id": "nope", "component_id": "x"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")

    def test_structured_ui_survives_get_messages(self) -> None:
        sid = self._create_session()
        self.client.post(
            f"/api/sessions/{sid}/ui-events",
            headers=self.headers,
            json={"action_id": "start", "component_id": "bootstrap"},
        )
        listed = self.client.get(
            f"/api/sessions/{sid}/messages",
            headers=self.headers,
        )
        assistant = next(m for m in listed.json()["messages"] if m["role"] == "assistant")
        self.assertEqual(assistant["structured_ui"]["screen"]["type"], "vstack")


if __name__ == "__main__":
    unittest.main()
