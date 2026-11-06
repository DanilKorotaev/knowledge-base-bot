"""Ingress API: tokens, adapters, rules, delivery of external messages."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from kb_app_api.tests import test_smoke as smoke  # noqa: E402
from kb_app_api.tests.auth_test_helpers import bearer_headers  # noqa: E402


def setUpModule() -> None:
    smoke.setUpModule()
    os.environ["KB_APP_API_BYPASS_ACCESS_CHECK"] = "true"


def tearDownModule() -> None:
    smoke.tearDownModule()


@unittest.skipUnless(TestClient is not None, "Нужен fastapi")
class TestIngressApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from config import config

        config.KB_APP_JWT_SECRET = os.environ.get("KB_APP_JWT_SECRET", "smoke-test-jwt-secret")
        config.ACCESS_MODE = "open"
        config.KB_APP_API_BYPASS_ACCESS_CHECK = True
        config.DB_TYPE = "sqlite"
        config.DB_FILE = os.environ["DB_FILE"]
        config.LOCAL_KB_PATH = Path(os.environ["LOCAL_KB_PATH"])
        config.KB_APP_QUERY_JOBS_ENABLED = False

        import utils.db_helpers as db_helpers

        db_helpers._db_instance = None  # type: ignore[attr-defined]

        from kb_app_api.main import app

        cls.client = TestClient(app)
        cls.headers = bearer_headers(cls.client, login="ingress_tester")

    def test_create_token_and_ingest_to_session(self) -> None:
        session = self.client.post(
            "/api/sessions",
            headers=self.headers,
            json={"title": "Ingress target"},
        )
        self.assertEqual(session.status_code, 201, session.text)
        session_id = session.json()["session"]["id"]

        binding = self.client.put(
            "/api/me/ingress/bindings",
            headers=self.headers,
            json={"binding_key": "default", "session_id": int(session_id)},
        )
        self.assertEqual(binding.status_code, 200, binding.text)

        rule = self.client.post(
            "/api/me/ingress/rules",
            headers=self.headers,
            json={
                "label": "all to default",
                "priority": 10,
                "match": {},
                "action": {
                    "kind": "session",
                    "session_key": "default",
                    "policy": "ingest_only",
                },
            },
        )
        self.assertEqual(rule.status_code, 200, rule.text)

        adapter = self.client.put(
            "/api/me/ingress/adapters",
            headers=self.headers,
            json={
                "key": "demo_source",
                "label": "Demo Source",
                "participant_key": "demo_source",
                "config": {},
            },
        )
        self.assertEqual(adapter.status_code, 200, adapter.text)

        token_resp = self.client.post(
            "/api/me/ingress/tokens",
            headers=self.headers,
            json={
                "label": "CI: demo-repo",
                "description": "GitHub Actions demo-repo → secret KBAPP_INGRESS_URL",
                "channel_id": "ci",
                "adapter_key": "demo_source",
                "allow_enqueue_agent": False,
                "agent_runtime": "none",
            },
        )
        self.assertEqual(token_resp.status_code, 200, token_resp.text)
        body_tok = token_resp.json()
        raw = body_tok["token"]
        self.assertTrue(raw)
        self.assertEqual(body_tok.get("label"), "CI: demo-repo")
        self.assertIn("demo-repo", body_tok.get("description") or "")

        ingest = self.client.post(
            f"/api/ingress/{raw}",
            json={
                "source": "demo",
                "type": "demo.ping",
                "summary": "Hello from ingress",
                "detail": "expanded detail body",
                "dedupe_key": "demo-1",
                "payload": {"n": 1},
            },
        )
        self.assertEqual(ingest.status_code, 200, ingest.text)
        body = ingest.json()
        self.assertTrue(body.get("ok"), body)
        self.assertFalse(body.get("deduped"))

        msgs = self.client.get(
            f"/api/sessions/{session_id}/messages",
            headers=self.headers,
        )
        self.assertEqual(msgs.status_code, 200, msgs.text)
        messages = msgs.json()["messages"]
        external = [m for m in messages if m.get("role") == "external"]
        self.assertTrue(external, messages)
        last = external[-1]
        self.assertEqual(last.get("content"), "Hello from ingress")
        self.assertEqual(last["external"].get("summary"), "Hello from ingress")
        self.assertEqual(last["external"].get("detail"), "expanded detail body")
        self.assertEqual(last["external"]["participant"]["label"], "Demo Source")

        again = self.client.post(
            f"/api/ingress/{raw}",
            json={
                "source": "demo",
                "type": "demo.ping",
                "summary": "Hello from ingress",
                "dedupe_key": "demo-1",
            },
        )
        self.assertEqual(again.status_code, 200, again.text)
        self.assertTrue(again.json().get("deduped"))

    def test_upload_and_fetch_avatar(self) -> None:
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
            b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        upload = self.client.post(
            "/api/me/ingress/avatars",
            headers=self.headers,
            data={"participant_key": "ci"},
            files={"file": ("ci.png", png, "image/png")},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        asset = upload.json()["avatar"]
        asset_id = asset["id"]
        self.assertTrue(asset_id)
        got = self.client.get(f"/api/ingress/avatars/{asset_id}")
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, png)

    def test_revoke_token_returns_404(self) -> None:
        token_resp = self.client.post(
            "/api/me/ingress/tokens",
            headers=self.headers,
            json={"label": "temp", "description": "revoke test"},
        )
        self.assertEqual(token_resp.status_code, 200, token_resp.text)
        token_id = token_resp.json()["id"]
        raw = token_resp.json()["token"]

        revoked = self.client.post(
            f"/api/me/ingress/tokens/{token_id}/revoke",
            headers=self.headers,
        )
        self.assertEqual(revoked.status_code, 200, revoked.text)

        ingest = self.client.post(
            f"/api/ingress/{raw}",
            json={"summary": "should fail"},
        )
        self.assertEqual(ingest.status_code, 404)

    def test_extract_session_from_hint_regex(self) -> None:
        from kb_app_api.ingress.router import resolve_action, select_rule

        rules = [
            {
                "id": "r1",
                "enabled": True,
                "priority": 1,
                "match": {"source": "ci"},
                "extract": {
                    "regex": {
                        "session_id": {
                            "path": "hints.commit_message",
                            "pattern": r"KB-Session:\s*(\d+)",
                            "group": 1,
                        }
                    }
                },
                "action": {"kind": "session", "policy": "ingest_only"},
            }
        ]
        envelope = {
            "source": "ci",
            "type": "ci.failed",
            "hints": {"commit_message": "fix stuff\n\nKB-Session: 42\n"},
        }
        token = {
            "channel_id": "ci",
            "allow_enqueue_agent": False,
            "allow_script": False,
        }
        rule = select_rule(rules, envelope=envelope, token=token)
        self.assertIsNotNone(rule)
        action = resolve_action(rule=rule, envelope=envelope, token=token)
        self.assertEqual(action["session_id"], "42")
        self.assertEqual(action["kind"], "session")


class TestIngressRouterUnit(unittest.TestCase):
    def test_token_sandbox_blocks_enqueue(self) -> None:
        from kb_app_api.ingress.router import resolve_action

        rule = {
            "id": "r",
            "extract": {},
            "action": {
                "kind": "session",
                "session_id": "9",
                "policy": "enqueue_agent",
            },
        }
        token = {
            "allow_enqueue_agent": False,
            "allow_script": False,
            "agent_runtime": "none",
        }
        action = resolve_action(rule=rule, envelope={}, token=token)
        self.assertEqual(action["policy"], "ingest_only")


if __name__ == "__main__":
    unittest.main()
