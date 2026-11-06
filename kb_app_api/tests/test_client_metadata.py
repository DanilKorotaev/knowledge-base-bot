"""Tests for optional iOS client metadata headers and agent env mapping."""

from __future__ import annotations

import unittest

from kb_app_api.client_metadata import (
    agent_context_from_json,
    agent_context_to_json,
    agent_env_from_client_meta,
    build_agent_context,
    client_meta_from_headers,
)


class TestClientMetadata(unittest.TestCase):
    def test_extracts_kb_headers(self) -> None:
        headers = {
            "X-KB-App-Version": "1.2.3",
            "X-KB-App-Build": "42",
            "X-KB-App-Platform": "ios",
            "X-KB-App-OS": "18.5",
            "X-KB-App-Log-Session": "abc-log-session",
            "X-KB-App-Timezone": "Europe/Moscow",
            "X-KB-App-Locale": "ru",
            "User-Agent": "KnowledgeBaseApp/1.2.3 (ios 18.5; build 42)",
        }
        meta = client_meta_from_headers(headers)
        self.assertEqual(meta["x-kb-app-version"], "1.2.3")
        self.assertEqual(meta["x-kb-app-build"], "42")
        self.assertEqual(meta["x-kb-app-platform"], "ios")
        self.assertEqual(meta["x-kb-app-os"], "18.5")
        self.assertEqual(meta["x-kb-app-log-session"], "abc-log-session")
        self.assertEqual(meta["x-kb-app-timezone"], "Europe/Moscow")
        self.assertEqual(meta["x-kb-app-locale"], "ru")
        self.assertIn("KnowledgeBaseApp/1.2.3", meta["user-agent"])

    def test_missing_headers_ok(self) -> None:
        meta = client_meta_from_headers({})
        self.assertEqual(meta, {})

    def test_agent_env_from_client_meta(self) -> None:
        env = agent_env_from_client_meta(
            {
                "x-kb-app-version": "1.0.0",
                "x-kb-app-timezone": "Europe/Moscow",
                "x-kb-app-locale": "ru_RU",
            }
        )
        self.assertEqual(env["KB_APP_VERSION"], "1.0.0")
        self.assertEqual(env["KB_CLIENT_TZ"], "Europe/Moscow")
        self.assertEqual(env["KB_CLIENT_LOCALE"], "ru_RU")
        self.assertNotIn("KB_APP_BUILD", env)

    def test_build_agent_context_merges(self) -> None:
        ctx = build_agent_context(
            channel="app",
            user_id=7,
            session_id=99,
            client_meta={"x-kb-app-timezone": "UTC", "x-kb-app-locale": "en"},
        )
        self.assertEqual(ctx["KB_CHANNEL"], "app")
        self.assertEqual(ctx["KB_USER_ID"], "7")
        self.assertEqual(ctx["KB_SESSION_ID"], "99")
        self.assertEqual(ctx["KB_CLIENT_TZ"], "UTC")
        self.assertEqual(ctx["KB_CLIENT_LOCALE"], "en")

    def test_agent_context_json_roundtrip(self) -> None:
        raw = agent_context_to_json({"KB_SESSION_ID": "3", "KB_CLIENT_TZ": "UTC"})
        self.assertIsNotNone(raw)
        back = agent_context_from_json(raw)
        self.assertEqual(back["KB_SESSION_ID"], "3")
        self.assertEqual(back["KB_CLIENT_TZ"], "UTC")


if __name__ == "__main__":
    unittest.main()
