"""ISO 8601 UTC с суффиксом Z для JSON API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def to_iso_z(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return str(value)
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
