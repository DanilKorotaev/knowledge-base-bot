"""Agent code workspaces under AGENT_ROOT (mirrors + leased slots).

Layout::

    $AGENT_ROOT/workspaces/
      mirrors/<repo_id>.git/     # bare
      slots/<slot_id>/
        repo/                    # worktree
        lease.json

No personal repo names here — callers pass repo_id + remote_url.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
SLOT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}$")
DEFAULT_TTL_DAYS = 7


class WorkspaceError(ValueError):
    """User-facing contract / filesystem error."""


@dataclass
class Lease:
    slot_id: str
    repo_id: str
    remote_url: str
    branch: str
    session_id: Optional[str]
    leased_at: str
    last_used_at: str
    delete_after: str
    status: str = "leased"  # leased | free

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "repo_id": self.repo_id,
            "remote_url": self.remote_url,
            "branch": self.branch,
            "session_id": self.session_id,
            "leased_at": self.leased_at,
            "last_used_at": self.last_used_at,
            "delete_after": self.delete_after,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Lease":
        return cls(
            slot_id=str(data.get("slot_id") or ""),
            repo_id=str(data.get("repo_id") or ""),
            remote_url=str(data.get("remote_url") or ""),
            branch=str(data.get("branch") or ""),
            session_id=(str(data["session_id"]) if data.get("session_id") else None),
            leased_at=str(data.get("leased_at") or ""),
            last_used_at=str(data.get("last_used_at") or ""),
            delete_after=str(data.get("delete_after") or ""),
            status=str(data.get("status") or "leased"),
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_repo_id(repo_id: str) -> str:
    text = (repo_id or "").strip()
    if not REPO_ID_RE.match(text):
        raise WorkspaceError(
            "repo_id must match ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$ "
            f"(got {repo_id!r})"
        )
    return text


def validate_slot_id(slot_id: str) -> str:
    text = (slot_id or "").strip()
    if not SLOT_ID_RE.match(text):
        raise WorkspaceError(f"invalid slot_id: {slot_id!r}")
    return text


def resolve_agent_root(explicit: Optional[str] = None) -> Path:
    raw = (explicit or os.environ.get("AGENT_ROOT") or "").strip()
    if not raw:
        raise WorkspaceError(
            "AGENT_ROOT is not set. Host should export per-user AGENT_ROOT "
            "(see AGENT_ROOT_BASE + users/<login>)."
        )
    root = Path(raw).expanduser().resolve()
    if not root.is_absolute():
        raise WorkspaceError(f"AGENT_ROOT must be absolute (got {root})")
    return root


def workspaces_dir(agent_root: Path) -> Path:
    return agent_root / "workspaces"


def mirrors_dir(agent_root: Path) -> Path:
    return workspaces_dir(agent_root) / "mirrors"


def slots_dir(agent_root: Path) -> Path:
    return workspaces_dir(agent_root) / "slots"


def mirror_path(agent_root: Path, repo_id: str) -> Path:
    return mirrors_dir(agent_root) / f"{repo_id}.git"


def slot_path(agent_root: Path, slot_id: str) -> Path:
    return slots_dir(agent_root) / slot_id


def lease_path(slot_dir: Path) -> Path:
    return slot_dir / "lease.json"


def repo_checkout_path(slot_dir: Path) -> Path:
    return slot_dir / "repo"


def ensure_layout(agent_root: Path) -> None:
    mirrors_dir(agent_root).mkdir(parents=True, exist_ok=True)
    slots_dir(agent_root).mkdir(parents=True, exist_ok=True)


def _run_git(args: list[str], *, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", *args]
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise WorkspaceError(f"git {' '.join(args)} failed: {err or result.returncode}")
    return result


def _read_lease(slot_dir: Path) -> Optional[Lease]:
    path = lease_path(slot_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    lease = Lease.from_dict(data)
    if not lease.slot_id:
        lease.slot_id = slot_dir.name
    return lease


def _write_lease(slot_dir: Path, lease: Lease) -> None:
    path = lease_path(slot_dir)
    path.write_text(
        json.dumps(lease.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _ensure_mirror(agent_root: Path, repo_id: str, remote_url: str) -> Path:
    mirror = mirror_path(agent_root, repo_id)
    if mirror.is_dir():
        # Keep remote URL in sync if caller passes a new one.
        _run_git(["remote", "set-url", "origin", remote_url], cwd=mirror, check=False)
        _run_git(["fetch", "--prune", "origin"], cwd=mirror)
        return mirror
    mirrors_dir(agent_root).mkdir(parents=True, exist_ok=True)
    parent = mirror.parent
    _run_git(["clone", "--bare", remote_url, str(mirror)], cwd=parent)
    return mirror


def _rev_exists(mirror: Path, rev: str) -> bool:
    probe = _run_git(["rev-parse", "--verify", "--quiet", rev], cwd=mirror, check=False)
    return probe.returncode == 0


def _commitish_for_branch(mirror: Path, branch: str) -> str:
    """Resolve a branch name to a commit-ish present in the bare mirror."""
    candidates = (
        f"refs/remotes/origin/{branch}",
        f"origin/{branch}",
        f"refs/heads/{branch}",
        branch,
    )
    for rev in candidates:
        if _rev_exists(mirror, rev):
            return rev
    raise WorkspaceError(f"branch not found in mirror: {branch}")


def _default_branch(mirror: Path, preferred: Optional[str]) -> str:
    if preferred and preferred.strip():
        return preferred.strip()
    sym = _run_git(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=mirror, check=False)
    if sym.returncode == 0:
        ref = (sym.stdout or "").strip()
        if ref.startswith("origin/"):
            return ref[len("origin/") :]
        if ref:
            return ref
    head = _run_git(["symbolic-ref", "--short", "HEAD"], cwd=mirror, check=False)
    if head.returncode == 0 and (head.stdout or "").strip():
        return (head.stdout or "").strip()
    for candidate in ("main", "master", "develop"):
        try:
            _commitish_for_branch(mirror, candidate)
            return candidate
        except WorkspaceError:
            continue
    raise WorkspaceError("cannot detect default branch; pass branch= explicitly")


def _list_slot_dirs(agent_root: Path) -> list[Path]:
    root = slots_dir(agent_root)
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir())


def _find_reusable_slot(
    agent_root: Path,
    *,
    repo_id: str,
    session_id: Optional[str],
) -> Optional[Path]:
    free_for_repo: Optional[Path] = None
    for slot_dir in _list_slot_dirs(agent_root):
        lease = _read_lease(slot_dir)
        if lease is None or lease.repo_id != repo_id:
            continue
        checkout = repo_checkout_path(slot_dir)
        if not checkout.is_dir():
            continue
        if session_id and lease.session_id == session_id and lease.status == "leased":
            return slot_dir
        if lease.status == "free" and free_for_repo is None:
            free_for_repo = slot_dir
    return free_for_repo


def _new_slot_id(repo_id: str) -> str:
    short = uuid.uuid4().hex[:8]
    return f"{repo_id}-{short}"


def _local_branch_name(slot_id: str) -> str:
    # Unique per slot so multiple checkouts of the same logical branch coexist.
    return f"workspace/{slot_id}"


def _attach_worktree(mirror: Path, checkout: Path, branch: str, slot_id: str) -> None:
    if checkout.exists():
        shutil.rmtree(checkout)
    start_point = _commitish_for_branch(mirror, branch)
    local_branch = _local_branch_name(slot_id)
    _run_git(
        [
            "worktree",
            "add",
            "--force",
            "-B",
            local_branch,
            str(checkout),
            start_point,
        ],
        cwd=mirror,
    )


def _refresh_checkout(mirror: Path, checkout: Path, branch: str, slot_id: str) -> None:
    _run_git(["fetch", "--prune", "origin"], cwd=mirror, check=False)
    if not checkout.is_dir():
        _attach_worktree(mirror, checkout, branch, slot_id)
        return
    start_point = _commitish_for_branch(mirror, branch)
    local_branch = _local_branch_name(slot_id)
    _run_git(["checkout", "-B", local_branch, start_point], cwd=checkout)
    _run_git(["reset", "--hard", start_point], cwd=checkout)
    _run_git(["clean", "-fd"], cwd=checkout)


def ensure_workspace(
    repo_id: str,
    remote_url: str,
    *,
    branch: Optional[str] = None,
    session_id: Optional[str] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    agent_root: Optional[Path] = None,
) -> dict[str, Any]:
    """Ensure a leased worktree for repo_id; return path + lease metadata."""
    repo_id = validate_repo_id(repo_id)
    remote = (remote_url or "").strip()
    if not remote:
        raise WorkspaceError("remote_url is required")
    if ttl_days < 1:
        raise WorkspaceError("ttl_days must be >= 1")

    root = agent_root or resolve_agent_root()
    ensure_layout(root)
    mirror = _ensure_mirror(root, repo_id, remote)
    resolved_branch = _default_branch(mirror, branch)
    sid = (session_id or os.environ.get("KB_SESSION_ID") or "").strip() or None

    slot_dir = _find_reusable_slot(root, repo_id=repo_id, session_id=sid)
    created = False
    if slot_dir is None:
        slot_id = _new_slot_id(repo_id)
        slot_dir = slot_path(root, slot_id)
        slot_dir.mkdir(parents=True, exist_ok=False)
        created = True
    else:
        slot_id = slot_dir.name

    checkout = repo_checkout_path(slot_dir)
    if created or not checkout.is_dir():
        _attach_worktree(mirror, checkout, resolved_branch, slot_id)
    else:
        _refresh_checkout(mirror, checkout, resolved_branch, slot_id)

    now = _utc_now()
    delete_after = _iso(now + timedelta(days=ttl_days))
    existing = _read_lease(slot_dir)
    leased_at = existing.leased_at if existing and existing.leased_at else _iso(now)
    lease = Lease(
        slot_id=slot_id,
        repo_id=repo_id,
        remote_url=remote,
        branch=resolved_branch,
        session_id=sid,
        leased_at=leased_at,
        last_used_at=_iso(now),
        delete_after=delete_after,
        status="leased",
    )
    _write_lease(slot_dir, lease)
    return {
        "ok": True,
        "path": str(checkout.resolve()),
        "slot_id": slot_id,
        "repo_id": repo_id,
        "branch": resolved_branch,
        "mirror": str(mirror.resolve()),
        "lease": lease.to_dict(),
        "created": created,
        "agent_root": str(root),
    }


def release_workspace(
    slot_id: str,
    *,
    agent_root: Optional[Path] = None,
    delete_worktree: bool = False,
) -> dict[str, Any]:
    """Mark slot free; optionally remove the worktree (mirror kept)."""
    slot_id = validate_slot_id(slot_id)
    root = agent_root or resolve_agent_root()
    slot_dir = slot_path(root, slot_id)
    if not slot_dir.is_dir():
        raise WorkspaceError(f"slot not found: {slot_id}")
    lease = _read_lease(slot_dir) or Lease(
        slot_id=slot_id,
        repo_id="",
        remote_url="",
        branch="",
        session_id=None,
        leased_at=_iso(_utc_now()),
        last_used_at=_iso(_utc_now()),
        delete_after=_iso(_utc_now()),
        status="free",
    )
    lease.status = "free"
    lease.session_id = None
    lease.last_used_at = _iso(_utc_now())
    _write_lease(slot_dir, lease)

    removed = False
    checkout = repo_checkout_path(slot_dir)
    if delete_worktree and checkout.exists():
        # Prefer git worktree remove when linked to a mirror.
        if lease.repo_id:
            mirror = mirror_path(root, lease.repo_id)
            if mirror.is_dir():
                _run_git(
                    ["worktree", "remove", "--force", str(checkout)],
                    cwd=mirror,
                    check=False,
                )
        if checkout.exists():
            shutil.rmtree(checkout)
        removed = True

    return {
        "ok": True,
        "slot_id": slot_id,
        "status": "free",
        "worktree_removed": removed,
        "lease": lease.to_dict(),
    }


def list_workspaces(*, agent_root: Optional[Path] = None) -> dict[str, Any]:
    root = agent_root or resolve_agent_root()
    ensure_layout(root)
    slots: list[dict[str, Any]] = []
    for slot_dir in _list_slot_dirs(root):
        lease = _read_lease(slot_dir)
        checkout = repo_checkout_path(slot_dir)
        slots.append(
            {
                "slot_id": slot_dir.name,
                "path": str(checkout.resolve()) if checkout.exists() else None,
                "lease": lease.to_dict() if lease else None,
            }
        )
    mirrors = sorted(p.name for p in mirrors_dir(root).iterdir() if p.is_dir()) if mirrors_dir(root).is_dir() else []
    return {
        "ok": True,
        "agent_root": str(root),
        "mirrors": mirrors,
        "slots": slots,
    }
