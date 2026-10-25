"""Unit tests for per-user vault path helpers."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


class TestVaultPaths(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        os.environ["LOCAL_KB_PATH"] = self._tmpdir
        import config as config_mod

        config_mod.config.LOCAL_KB_PATH = Path(self._tmpdir)

    def test_resolve_kb_root_and_agent_isolation(self) -> None:
        from kb_app_api.vault_paths import (
            localize_file_changes,
            resolve_agent_kb_root,
            resolve_kb_root,
            vault_relative_for_login,
        )

        user = {
            "id": 1,
            "login": "alice",
            "vault_root_relative": vault_relative_for_login("alice"),
            "cursor_isolation": "strict",
        }
        vault = resolve_kb_root(user)
        self.assertEqual(vault, (Path(self._tmpdir) / "users" / "alice").resolve())
        self.assertEqual(resolve_agent_kb_root(user), vault)

        host_user = dict(user, cursor_isolation="host")
        self.assertEqual(resolve_agent_kb_root(host_user), Path(self._tmpdir).resolve())

        from kb_app_api.vault_paths import is_per_user_vault_path

        self.assertTrue(is_per_user_vault_path(vault))
        self.assertFalse(is_per_user_vault_path(Path(self._tmpdir)))
        self.assertFalse(is_per_user_vault_path(Path(self._tmpdir) / "users"))

        changes = localize_file_changes(
            [{"path": "HealthData/a.json", "type": "modified"}],
            vault,
        )
        self.assertEqual(changes[0]["path"], "users/alice/HealthData/a.json")

    def test_to_vault_relative(self) -> None:
        from kb_app_api.vault_paths import (
            changes_to_vault_relative,
            to_vault_relative,
            vault_relative_for_login,
        )

        user = {
            "login": "alice",
            "vault_root_relative": vault_relative_for_login("alice"),
        }
        self.assertEqual(
            to_vault_relative(user, "users/alice/HealthData/a.json"),
            "HealthData/a.json",
        )
        self.assertEqual(to_vault_relative(user, "users/alice"), "")
        self.assertEqual(to_vault_relative(user, "notes/x.md"), "notes/x.md")
        mapped = changes_to_vault_relative(
            user, [{"path": "users/alice/a.md", "type": "modified"}]
        )
        self.assertEqual(mapped[0]["path"], "a.md")


class TestNextCloudForUser(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["KB_APP_JWT_SECRET"] = "vault-nc-jwt"
        os.environ["NEXTCLOUD_URL"] = "https://nc.example"
        os.environ.pop("KB_NC_TOKEN_KEY", None)
        import config as config_mod

        config_mod.config.KB_APP_JWT_SECRET = "vault-nc-jwt"
        config_mod.config.KB_NC_TOKEN_KEY = None
        config_mod.config.NEXTCLOUD_URL = "https://nc.example"
        config_mod.config.NEXTCLOUD_BOT_USERNAME = "bot"
        config_mod.config.NEXTCLOUD_BOT_PASSWORD = "botpw"

    def test_for_user_uses_app_password_and_kb_folder(self) -> None:
        from kb_app_api.nc_token_crypto import encrypt_nc_token
        from services.nextcloud_service import NextCloudService
        from services.sync_service import SyncService

        enc = encrypt_nc_token("user-app-pw")
        user = {
            "id": 1,
            "login": "alice",
            "nextcloud_username": "alice",
            "nc_app_password_enc": enc,
            "kb_folder": "/KnowledgeBase",
            "vault_root_relative": "users/alice",
        }
        nc = NextCloudService.for_user(user)
        self.assertIsNotNone(nc)
        assert nc is not None
        self.assertTrue(nc.enabled)
        self.assertEqual(nc.username, "alice")
        self.assertEqual(nc.password, "user-app-pw")
        self.assertEqual(nc.base_path, "KnowledgeBase")
        self.assertIn("/dav/files/alice", nc.webdav_url)

        sync = SyncService.for_user(user)
        self.assertTrue(sync.enabled)
        self.assertEqual(sync.nextcloud_service.username, "alice")
        self.assertEqual(sync.nextcloud_service.base_path, "KnowledgeBase")

    def test_for_user_without_token_disables_sync(self) -> None:
        from services.nextcloud_service import NextCloudService
        from services.sync_service import SyncService

        user = {
            "id": 2,
            "login": "bob",
            "vault_root_relative": "users/bob",
            "nc_app_password_enc": None,
        }
        self.assertIsNone(NextCloudService.for_user(user))
        sync = SyncService.for_user(user)
        self.assertFalse(sync.enabled)


if __name__ == "__main__":
    unittest.main()
