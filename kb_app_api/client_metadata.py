"""Capture optional iOS client version headers for logging."""

from __future__ import annotations

from typing import Mapping

_HEADER_KEYS = (
    "x-kb-app-version",
    "x-kb-app-build",
    "x-kb-app-platform",
    "x-kb-app-os",
)


def client_meta_from_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Extract known X-KB-App-* headers (keys compared case-insensitively)."""
    lower = {str(key).lower(): str(value).strip() for key, value in headers.items() if value}
    meta: dict[str, str] = {}
    for key in _HEADER_KEYS:
        value = lower.get(key)
        if value:
            meta[key] = value
    ua = lower.get("user-agent")
    if ua:
        meta["user-agent"] = ua
    return meta
