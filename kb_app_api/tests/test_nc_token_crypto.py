"""Encrypt / decrypt Nextcloud App Passwords."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestNcTokenCrypto(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["KB_APP_JWT_SECRET"] = "crypto-unit-jwt"
        os.environ.pop("KB_NC_TOKEN_KEY", None)
        # Reload config-dependent helpers via fresh import path is fine —
        # encrypt uses live config attributes.
        from config import config

        config.KB_APP_JWT_SECRET = "crypto-unit-jwt"
        config.KB_NC_TOKEN_KEY = None

    def test_roundtrip_derived_key(self) -> None:
        from kb_app_api.nc_token_crypto import decrypt_nc_token, encrypt_nc_token

        token = "NcApp-Pass-Word-xyz"
        enc = encrypt_nc_token(token)
        self.assertNotEqual(enc, token)
        self.assertEqual(decrypt_nc_token(enc), token)

    def test_explicit_passphrase_key(self) -> None:
        from config import config
        from kb_app_api.nc_token_crypto import decrypt_nc_token, encrypt_nc_token

        config.KB_NC_TOKEN_KEY = "staging-passphrase-not-fernet"
        enc = encrypt_nc_token("secret-app-pw")
        self.assertEqual(decrypt_nc_token(enc), "secret-app-pw")

    def test_wrong_key_fails(self) -> None:
        from config import config
        from kb_app_api.nc_token_crypto import decrypt_nc_token, encrypt_nc_token

        config.KB_NC_TOKEN_KEY = "key-a"
        enc = encrypt_nc_token("pw")
        config.KB_NC_TOKEN_KEY = "key-b"
        with self.assertRaises(ValueError):
            decrypt_nc_token(enc)


class TestKbFolder(unittest.TestCase):
    def test_normalize(self) -> None:
        from kb_app_api.kb_folder import normalize_kb_folder

        self.assertEqual(normalize_kb_folder(None), "/")
        self.assertEqual(normalize_kb_folder(""), "/")
        self.assertEqual(normalize_kb_folder("notes"), "/notes")
        self.assertEqual(normalize_kb_folder("/a/b/"), "/a/b")
        self.assertEqual(normalize_kb_folder("/./x"), "/x")

    def test_rejects_dotdot(self) -> None:
        from kb_app_api.errors import APIError
        from kb_app_api.kb_folder import normalize_kb_folder

        with self.assertRaises(APIError):
            normalize_kb_folder("/a/../b")


class TestMintAppPassword(unittest.TestCase):
    def test_mint_parses_ocs(self) -> None:
        from unittest.mock import MagicMock, patch

        from config import config

        config.KB_APP_NC_PROVISION_ENABLED = True
        config.NEXTCLOUD_URL = "https://nc.example"
        config.NEXTCLOUD_BOT_USERNAME = "bot"
        config.NEXTCLOUD_BOT_PASSWORD = "botpw"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ocs": {"data": {"apppassword": "APP-TOKEN-1"}, "meta": {"statuscode": 200}}
        }
        with patch("kb_app_api.nextcloud_provision.requests.get", return_value=mock_resp) as get:
            from kb_app_api.nextcloud_provision import mint_nextcloud_app_password

            pw = mint_nextcloud_app_password(userid="alice", password="loginpw", retries=1)
            self.assertEqual(pw, "APP-TOKEN-1")
            get.assert_called_once()
            args, kwargs = get.call_args
            self.assertIn("getapppassword", args[0])
            self.assertEqual(kwargs["auth"].username, "alice")


if __name__ == "__main__":
    unittest.main()
