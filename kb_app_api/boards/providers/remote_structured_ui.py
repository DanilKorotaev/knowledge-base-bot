"""Remote Structured UI board — HTTPS fetch with host allowlist."""
from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from config import config

logger = logging.getLogger(__name__)

PROVIDER_ID = "remote_structured_ui"


def _host_allowed(host: str) -> bool:
    allow = {h.lower() for h in (config.BOARDS_REMOTE_HOST_ALLOWLIST or []) if h}
    if not allow:
        return False
    return host.lower() in allow


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "kb-boards-remote/1"})
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — host allowlisted
        raw = resp.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("remote payload must be a JSON object")
    return payload


def compute(
    board_meta: dict[str, Any],
    definition: dict[str, Any],
) -> dict[str, Any]:
    labels = definition.get("labels") or {}
    title = str(labels.get("title") or board_meta.get("title") or board_meta["id"])
    url = str(definition.get("url") or "").strip()
    period_ui = str(definition.get("period_ui") or "none").strip().lower()
    if period_ui not in ("none", "month", "range"):
        period_ui = "none"

    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    board = {
        "id": board_meta["id"],
        "title": board_meta.get("title") or title,
        "subtitle": board_meta.get("subtitle"),
        "icon": board_meta.get("icon"),
        "kind": board_meta.get("kind") or "remote",
        "sort_order": int(board_meta.get("sort_order") or 0),
        "enabled": bool(board_meta.get("enabled", True)),
        "list_cell": {
            "kind": "status",
            "title": str(labels.get("list_title") or title),
            "subtitle": str(labels.get("list_subtitle") or board_meta.get("subtitle") or ""),
            "status": "ok",
            "status_label": str(labels.get("list_status") or "Remote"),
        },
        "rendered_at": rendered_at,
        "period_ui": period_ui,
    }

    def _error_doc(message: str) -> dict[str, Any]:
        return {
            "board": board,
            "document": {
                "schema_version": 1,
                "screen": {
                    "type": "vstack",
                    "id": "root",
                    "children": [
                        {"type": "text", "id": "title", "text": title},
                        {
                            "type": "callout",
                            "id": "err",
                            "text": message,
                            "variant": "warning",
                        },
                    ],
                },
            },
            "rendered_at": rendered_at,
            "period": "all",
            "from": None,
            "to": None,
        }

    if not url:
        return _error_doc(str(labels.get("err_missing_url") or "Remote URL is not configured"))

    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return _error_doc(str(labels.get("err_https") or "Remote URL must be https with a host"))
    if not _host_allowed(parsed.hostname):
        return _error_doc(
            str(labels.get("err_allowlist") or "Remote host is not in BOARDS_REMOTE_HOST_ALLOWLIST")
        )

    timeout = float(definition.get("timeout_sec") or config.BOARDS_REMOTE_TIMEOUT_SEC or 8)
    try:
        payload = _fetch_json(url, timeout=timeout)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("remote board fetch failed board_id=%s err=%s", board_meta.get("id"), exc)
        return _error_doc(str(labels.get("err_fetch") or f"Remote fetch failed: {exc}"))

    document: dict[str, Any] | None = None
    if isinstance(payload.get("document"), dict):
        document = deepcopy(payload["document"])
        remote_board = payload.get("board")
        if isinstance(remote_board, dict):
            if remote_board.get("list_cell"):
                board["list_cell"] = deepcopy(remote_board["list_cell"])
            if remote_board.get("subtitle"):
                board["subtitle"] = remote_board["subtitle"]
    elif payload.get("schema_version") is not None and isinstance(payload.get("screen"), dict):
        document = deepcopy(payload)
    elif isinstance(payload.get("screen"), dict):
        document = {"schema_version": 1, "screen": deepcopy(payload["screen"])}

    if document is None:
        return _error_doc(
            str(labels.get("err_shape") or "Remote JSON must include document or screen")
        )

    return {
        "board": board,
        "document": document,
        "rendered_at": rendered_at,
        "period": "all",
        "from": None,
        "to": None,
    }
