"""Sandboxed vault board script (read-only helpers, no imports).

definition.script_path: relative path under vault ending in ``.board.py``.
The file must define ``def build(ctx):`` returning either:
- a Structured UI document dict ``{schema_version, screen}``, or
- a list of child nodes, or
- ``{"children": [...], "list_cell": {...}, "title": "..."}``.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import config
from kb_app_api.boards.vault_io import VaultReadError, resolve_under_root

logger = logging.getLogger(__name__)

PROVIDER_ID = "vault_script"

_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "True": True,
    "False": False,
    "None": None,
}


class ScriptContext:
    """Read-only vault helpers exposed to board scripts."""

    def __init__(
        self,
        kb_root: Path,
        *,
        period: str | None,
        date_from: str | None,
        date_to: str | None,
        board_meta: dict[str, Any],
        definition: dict[str, Any],
    ) -> None:
        self._kb_root = kb_root
        self.period = period
        self.date_from = date_from
        self.date_to = date_to
        self.board = {
            "id": board_meta.get("id"),
            "title": board_meta.get("title"),
            "subtitle": board_meta.get("subtitle"),
        }
        self.labels = dict(definition.get("labels") or {})

    def read_json(self, relative: str) -> Any:
        path = resolve_under_root(self._kb_root, relative)
        if not path.is_file():
            raise FileNotFoundError(relative)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_json(self, relative: str) -> list[dict[str, Any]]:
        folder = resolve_under_root(self._kb_root, relative)
        if not folder.is_dir():
            return []
        out: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                out.append(payload)
        return out


def _run_script(source: str, ctx: ScriptContext) -> Any:
    globals_dict: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
    locals_dict: dict[str, Any] = {}
    exec(compile(source, "<board_script>", "exec"), globals_dict, locals_dict)  # noqa: S102
    build = locals_dict.get("build") or globals_dict.get("build")
    if not callable(build):
        raise ValueError("board script must define build(ctx)")
    return build(ctx)


def compute(
    kb_root: Path,
    board_meta: dict[str, Any],
    definition: dict[str, Any],
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    labels = definition.get("labels") or {}
    title = str(labels.get("title") or board_meta.get("title") or board_meta["id"])
    period_ui = str(definition.get("period_ui") or "none").strip().lower()
    if period_ui not in ("none", "month", "range"):
        period_ui = "none"
    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _board(list_cell: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": board_meta["id"],
            "title": board_meta.get("title") or title,
            "subtitle": board_meta.get("subtitle"),
            "icon": board_meta.get("icon"),
            "kind": board_meta.get("kind") or "cached_view",
            "sort_order": int(board_meta.get("sort_order") or 0),
            "enabled": bool(board_meta.get("enabled", True)),
            "list_cell": list_cell
            or {
                "kind": "status",
                "title": str(labels.get("list_title") or title),
                "subtitle": str(labels.get("list_subtitle") or ""),
                "status": "ok",
                "status_label": "Script",
            },
            "rendered_at": rendered_at,
            "period_ui": period_ui,
        }

    def _wrap(document: dict[str, Any], list_cell: dict[str, Any] | None = None) -> dict[str, Any]:
        scoped = bool(date_from or date_to) or (
            period not in (None, "", "all", "*", "range")
        )
        return {
            "board": _board(list_cell),
            "document": document,
            "rendered_at": rendered_at,
            "period": period or ("range" if scoped else "all"),
            "from": date_from,
            "to": date_to,
        }

    def _error(message: str) -> dict[str, Any]:
        return _wrap(
            {
                "schema_version": 1,
                "screen": {
                    "type": "vstack",
                    "id": "root",
                    "children": [
                        {"type": "text", "id": "title", "text": title},
                        {"type": "callout", "id": "err", "text": message, "variant": "warning"},
                    ],
                },
            }
        )

    script_path = str(definition.get("script_path") or "").strip()
    if not script_path.endswith(".board.py"):
        return _error(str(labels.get("err_path") or "script_path must end with .board.py"))
    try:
        path = resolve_under_root(kb_root, script_path)
    except VaultReadError as exc:
        return _error(str(exc))
    if not path.is_file():
        return _error(str(labels.get("err_missing") or f"Script not found: {script_path}"))

    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _error(str(exc))

    # Block obvious escapes / imports before exec.
    lowered = source.lower()
    for banned in ("import ", "__import__", "open(", "exec(", "eval(", "os.", "sys.", "subprocess"):
        if banned in lowered:
            return _error(str(labels.get("err_banned") or f"Script uses banned token: {banned}"))

    ctx = ScriptContext(
        kb_root,
        period=period,
        date_from=date_from,
        date_to=date_to,
        board_meta=board_meta,
        definition=definition,
    )
    timeout = float(config.BOARDS_VAULT_SCRIPT_TIMEOUT_SEC or 3)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_script, source, ctx)
            result = future.result(timeout=timeout)
    except FuturesTimeout:
        return _error(str(labels.get("err_timeout") or "Script timed out"))
    except Exception as exc:  # noqa: BLE001 — surface to board UI
        logger.warning("vault_script failed board_id=%s err=%s", board_meta.get("id"), exc)
        return _error(str(labels.get("err_runtime") or f"Script error: {exc}"))

    list_cell = None
    if isinstance(result, dict) and "schema_version" in result and "screen" in result:
        return _wrap(result)
    if isinstance(result, dict) and "children" in result:
        children = result.get("children")
        if not isinstance(children, list):
            return _error("build() children must be a list")
        if isinstance(result.get("list_cell"), dict):
            list_cell = result["list_cell"]
        doc_title = str(result.get("title") or title)
        return _wrap(
            {
                "schema_version": 1,
                "screen": {
                    "type": "vstack",
                    "id": "root",
                    "children": [{"type": "text", "id": "title", "text": doc_title}, *children],
                },
            },
            list_cell,
        )
    if isinstance(result, list):
        return _wrap(
            {
                "schema_version": 1,
                "screen": {
                    "type": "vstack",
                    "id": "root",
                    "children": [{"type": "text", "id": "title", "text": title}, *result],
                },
            }
        )
    return _error(str(labels.get("err_return") or "build() must return document, children, or list"))
