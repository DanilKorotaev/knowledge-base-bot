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
from kb_app_api.structured_ui.store import clear_all, get_for_message, set_for_message
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
        self.assertEqual(len(buttons), 2)

    def test_confirm_yes_stub_user_message(self) -> None:
        result = apply_mock_ui_event(action_id="confirm_yes", component_id="btn_yes")
        self.assertEqual(result.user_content, "[UI] Yes")

    def test_unknown_action_raises(self) -> None:
        with self.assertRaises(KeyError):
            apply_mock_ui_event(action_id="unknown", component_id="x")


@unittest.skipUnless(TestClient is not None, "Нужен fastapi (requirements.txt бота)")
class TestStructuredUIEventsHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = {"Authorization": "Bearer structured-ui-test-bearer"}

    def setUp(self) -> None:
        clear_all()

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

    def test_in_memory_store_roundtrip(self) -> None:
        doc = apply_mock_ui_event(action_id="start", component_id="bootstrap").screen
        set_for_message(42, doc)
        self.assertEqual(get_for_message(42), doc)


if __name__ == "__main__":
    unittest.main()
