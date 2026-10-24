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

        changes = localize_file_changes(
            [{"path": "HealthData/a.json", "type": "modified"}],
            vault,
        )
        self.assertEqual(changes[0]["path"], "users/alice/HealthData/a.json")


if __name__ == "__main__":
    unittest.main()
