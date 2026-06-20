"""Shared rules for skipping build artifacts and other non-KB paths during sync / change tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence

# Directory or file name segments that should never sync or be logged as KB edits.
_BUILD_ARTIFACT_DIR_NAMES = frozenset(
    {
        "test_output",
        "build_logs",
        "DerivedData",
        "xcresult",
    }
)

# Skip entire trees commonly produced by Xcode / fastlane / Ruby bundler.
_DEFAULT_ARTIFACT_PATH_SUBSTRINGS = (
    "fastlane/test_output/",
    "fastlane/build_logs/",
    "fastlane/screenshots/",
    "vendor/bundle/",
    "/build/",
    ".build/",
    ".swiftpm/",
)


def normalize_sync_path(path: str) -> str:
    return path.replace("\\", "/")


def is_excluded_sync_path(path: str, exclude_patterns: Optional[Sequence[str]] = None) -> bool:
    """
    Return True when a KB-relative path should be ignored for Nextcloud sync and change logging.

    Checks dot-segments, known artifact directories, and configured SYNC_EXCLUDE_PATTERNS.
    """
    if not path:
        return True

    normalized = normalize_sync_path(path)
    path_parts = Path(normalized).parts

    for part in path_parts:
        if part.startswith("."):
            return True
        if part in {"__pycache__", "node_modules", ".DS_Store"}:
            return True
        if part in _BUILD_ARTIFACT_DIR_NAMES:
            return True
        if part.endswith(".xcresult"):
            return True

    lowered = normalized.lower()
    for marker in _DEFAULT_ARTIFACT_PATH_SUBSTRINGS:
        if marker in lowered:
            return True

    if exclude_patterns:
        for pattern in exclude_patterns:
            pattern_clean = pattern.rstrip("/").rstrip("\\")
            if pattern_clean in path_parts:
                return True
            if "/" in pattern and pattern in normalized:
                return True
            if Path(normalized).name == pattern_clean:
                return True
            if pattern_clean.startswith("*.") and normalized.endswith(pattern_clean[1:]):
                return True

    return False


def sanitize_text_for_db(value: Optional[str], *, max_chars: int = 500_000) -> Optional[str]:
    """Make optional text safe for PostgreSQL UTF-8 text columns."""
    if value is None:
        return None
    cleaned = value.replace("\0", "")
    if len(cleaned) > max_chars:
        return cleaned[:max_chars] + "\n…[truncated]"
    return cleaned


def filter_trackable_changes(
    changes: Iterable[dict],
    exclude_patterns: Optional[Sequence[str]] = None,
) -> list[dict]:
    """Drop build artifacts and other excluded paths from Cursor CLI change lists."""
    kept: list[dict] = []
    for change in changes:
        path = change.get("path", "")
        if is_excluded_sync_path(path, exclude_patterns):
            continue
        sanitized = dict(change)
        sanitized["old_content"] = sanitize_text_for_db(change.get("old_content"))
        sanitized["new_content"] = sanitize_text_for_db(change.get("new_content"))
        kept.append(sanitized)
    return kept
