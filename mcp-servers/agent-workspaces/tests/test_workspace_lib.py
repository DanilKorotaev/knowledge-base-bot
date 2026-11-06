"""Unit tests for agent workspace layout / lease reuse (uses local git)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_PKG = Path(__file__).resolve().parents[1]
if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from workspace_lib import (  # noqa: E402
    WorkspaceError,
    ensure_workspace,
    list_workspaces,
    release_workspace,
    validate_repo_id,
)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _init_origin(path: Path) -> None:
    path.mkdir(parents=True)
    _git(["init", "-b", "main"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "Test"], path)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "README.md"], path)
    _git(["commit", "-m", "init"], path)


class TestWorkspaceLib(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = Path(tempfile.mkdtemp())
        self.origin = self._tmpdir / "origin"
        self.agent_root = self._tmpdir / "agent"
        _init_origin(self.origin)
        os.environ["AGENT_ROOT"] = str(self.agent_root)

    def test_validate_repo_id(self) -> None:
        self.assertEqual(validate_repo_id("bot"), "bot")
        with self.assertRaises(WorkspaceError):
            validate_repo_id("../x")
        with self.assertRaises(WorkspaceError):
            validate_repo_id("")

    def test_ensure_reuse_same_session(self) -> None:
        remote = str(self.origin)
        first = ensure_workspace("demo", remote, branch="main", session_id="s1")
        self.assertTrue(first["ok"])
        self.assertTrue(Path(first["path"]).is_dir())
        self.assertTrue((Path(first["path"]) / "README.md").is_file())

        second = ensure_workspace("demo", remote, branch="main", session_id="s1")
        self.assertEqual(first["slot_id"], second["slot_id"])
        self.assertEqual(first["path"], second["path"])
        self.assertFalse(second["created"])

        other = ensure_workspace("demo", remote, branch="main", session_id="s2")
        self.assertNotEqual(first["slot_id"], other["slot_id"])

        listed = list_workspaces()
        self.assertEqual(len(listed["slots"]), 2)
        self.assertIn("demo.git", listed["mirrors"])

        released = release_workspace(first["slot_id"])
        self.assertEqual(released["lease"]["status"], "free")

        reused = ensure_workspace("demo", remote, branch="main", session_id="s3")
        self.assertEqual(reused["slot_id"], first["slot_id"])

        lease = json.loads(
            (self.agent_root / "workspaces" / "slots" / first["slot_id"] / "lease.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(lease["status"], "leased")
        self.assertEqual(lease["session_id"], "s3")


if __name__ == "__main__":
    unittest.main()
