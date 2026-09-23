"""Seed / demo boards catalog (v1). Later: DB rows + vault compute.

Mirrors iOS `DemoBoardsCatalog` so TestFlight and API stay in sync until CRUD lands.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEMO_KPI_ID = "demo-kpi"
_DEMO_JOBS_ID = "demo-active-jobs"

_BOARDS: list[dict[str, Any]] = [
    {
        "id": _DEMO_KPI_ID,
        "title": "Demo: summary",
        "subtitle": "Sample metrics and table",
        "icon": "chart.bar",
        "kind": "cached_view",
        "sort_order": 10,
        "enabled": True,
        "list_cell": {
            "kind": "metrics",
            "title": "Demo: summary",
            "subtitle": "Sample metrics and table",
            "metrics": [
                {"label": "Total", "value": "12 450"},
                {"label": "Last", "value": "1 200"},
            ],
        },
        "rendered_at": "2026-08-27T12:00:00Z",
    },
    {
        "id": _DEMO_JOBS_ID,
        "title": "Demo: active jobs",
        "subtitle": "System board preview",
        "icon": "bolt.horizontal.circle",
        "kind": "system",
        "sort_order": 20,
        "enabled": True,
        "list_cell": {
            "kind": "status",
            "title": "Demo: active jobs",
            "subtitle": "System board preview",
            "status_text": "1 running",
            "status_tone": "info",
        },
        "rendered_at": "2026-08-27T12:00:00Z",
    },
]

_DOCUMENTS: dict[str, dict[str, Any]] = {
    _DEMO_KPI_ID: {
        "schema_version": 1,
        "screen": {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Demo summary"},
                {
                    "type": "callout",
                    "id": "hint",
                    "text": (
                        "This screen is driven by JSON from the server. "
                        "The app does not hardcode your knowledge base structure."
                    ),
                    "variant": "info",
                },
                {
                    "type": "hstack",
                    "id": "metrics_row",
                    "spacing": 12,
                    "children": [
                        {"type": "metric", "id": "m_total", "text": "12 450", "label": "Total"},
                        {"type": "metric", "id": "m_last", "text": "1 200", "label": "Last entry"},
                        {"type": "metric", "id": "m_count", "text": "18", "label": "Count"},
                    ],
                },
                {
                    "type": "table",
                    "id": "sample_table",
                    "label": "Recent rows",
                    "columns": [
                        {"id": "date", "label": "Date"},
                        {"id": "item", "label": "Item"},
                        {"id": "amount", "label": "Amount"},
                    ],
                    "rows": [
                        ["2026-08-20", "Alpha", "1 200"],
                        ["2026-08-12", "Beta", "890"],
                        ["2026-08-01", "Gamma", "450"],
                    ],
                },
            ],
        },
    },
    _DEMO_JOBS_ID: {
        "schema_version": 1,
        "screen": {
            "type": "vstack",
            "id": "root",
            "children": [
                {"type": "text", "id": "title", "text": "Active jobs"},
                {
                    "type": "callout",
                    "id": "status",
                    "text": "Demo only — real cancel/list arrives with query jobs API.",
                    "variant": "tip",
                },
                {
                    "type": "table",
                    "id": "jobs_table",
                    "label": "Running",
                    "columns": [
                        {"id": "session", "label": "Session"},
                        {"id": "status", "label": "Status"},
                        {"id": "duration", "label": "Duration"},
                    ],
                    "rows": [["Training plan", "running", "2m 14s"]],
                },
            ],
        },
    },
}


def list_boards(*, include_disabled: bool = False) -> list[dict[str, Any]]:
    boards = [deepcopy(b) for b in _BOARDS if include_disabled or b.get("enabled", True)]
    boards.sort(key=lambda b: int(b.get("sort_order") or 0))
    return boards


def get_board_detail(board_id: str) -> dict[str, Any] | None:
    board = next((deepcopy(b) for b in _BOARDS if b["id"] == board_id), None)
    if board is None:
        return None
    document = _DOCUMENTS.get(board_id)
    if document is None:
        return None
    return {
        "board": board,
        "document": deepcopy(document),
        "rendered_at": board.get("rendered_at"),
    }
