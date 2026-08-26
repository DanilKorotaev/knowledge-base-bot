"""Tests for optional iOS client metadata headers."""

from __future__ import annotations

import unittest

from kb_app_api.client_metadata import client_meta_from_headers


class TestClientMetadata(unittest.TestCase):
    def test_extracts_kb_headers(self) -> None:
        headers = {
            "X-KB-App-Version": "1.2.3",
            "X-KB-App-Build": "42",
            "X-KB-App-Platform": "ios",
            "X-KB-App-OS": "18.5",
            "User-Agent": "KnowledgeBaseApp/1.2.3 (ios 18.5; build 42)",
        }
        meta = client_meta_from_headers(headers)
        self.assertEqual(meta["x-kb-app-version"], "1.2.3")
        self.assertEqual(meta["x-kb-app-build"], "42")
        self.assertEqual(meta["x-kb-app-platform"], "ios")
        self.assertEqual(meta["x-kb-app-os"], "18.5")
        self.assertIn("KnowledgeBaseApp/1.2.3", meta["user-agent"])

    def test_missing_headers_ok(self) -> None:
        meta = client_meta_from_headers({})
        self.assertEqual(meta, {})


if __name__ == "__main__":
    unittest.main()
