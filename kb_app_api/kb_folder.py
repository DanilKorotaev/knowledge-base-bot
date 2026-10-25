"""Normalize user kb_folder paths (relative to NC user home)."""
from __future__ import annotations

from kb_app_api.errors import APIError


def normalize_kb_folder(raw: str | None) -> str:
    s = (raw or "/").strip() or "/"
    if "\\" in s or "\x00" in s:
        raise APIError(
            "validation_error",
            "kb_folder: недопустимые символы",
            detail="kb_folder",
            status_code=422,
        )
    if not s.startswith("/"):
        s = "/" + s
    parts: list[str] = []
    for p in s.split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            raise APIError(
                "validation_error",
                "kb_folder: путь не должен содержать ..",
                detail="kb_folder",
                status_code=422,
            )
        parts.append(p)
    return "/" + "/".join(parts) if parts else "/"
