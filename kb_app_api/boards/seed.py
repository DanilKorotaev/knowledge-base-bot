"""Default board rows seeded into the app DB (paths live here, not in provider code)."""
from __future__ import annotations

from typing import Any

# Seed data only — after insert, rows are editable in DB / via future agent tools.
DEFAULT_BOARDS: list[dict[str, Any]] = [
    {
        "id": "car-fuel",
        "title": "Авторасходы — топливо",
        "subtitle": "Соляра · только чтение",
        "icon": "fuelpump",
        "kind": "cached_view",
        "sort_order": 5,
        "enabled": 1,
        "definition": {
            "provider": "vault_frontmatter_agg",
            "path": "Документы/Тачки/Соляра/Расходы/Топливо",
            "filter": {"type": "fuel"},
            "fields": {
                "date": "date",
                "amount": "cost",
                "quantity": "liters",
                "label": "station",
            },
            "recent_limit": 10,
            "labels": {
                "title": "Соляра — топливо",
                "list_title": "Авторасходы — топливо",
                "list_subtitle": "Соляра · только чтение",
                "readonly": "Сводка только читает заметки из vault. Файлы не изменяются.",
                "metric_month": "Этот месяц",
                "metric_total": "Всего топливо",
                "metric_last": "Последняя",
                "metric_count": "Заправок",
                "table": "Последние заправки",
                "col_date": "Дата",
                "col_label": "АЗС",
                "col_qty": "Л",
                "col_amount": "Сумма",
                "currency": "₽",
            },
        },
    },
    {
        "id": "demo-kpi",
        "title": "Demo: summary",
        "subtitle": "Sample metrics and table",
        "icon": "chart.bar",
        "kind": "cached_view",
        "sort_order": 100,
        "enabled": 1,
        "definition": {"provider": "static"},
        "list_cell": {
            "kind": "metrics",
            "title": "Demo: summary",
            "subtitle": "Sample metrics and table",
            "metrics": [
                {"label": "Total", "value": "12 450"},
                {"label": "Last", "value": "1 200"},
            ],
        },
        "rendered_document": {
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
                        "scroll_horizontal": False,
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
        "rendered_at": "2026-08-27T12:00:00Z",
    },
    {
        "id": "demo-active-jobs",
        "title": "Demo: active jobs",
        "subtitle": "System board preview",
        "icon": "bolt.horizontal.circle",
        "kind": "system",
        "sort_order": 110,
        "enabled": 1,
        "definition": {"provider": "static"},
        "list_cell": {
            "kind": "status",
            "title": "Demo: active jobs",
            "subtitle": "System board preview",
            "status_text": "1 running",
            "status_tone": "info",
        },
        "rendered_document": {
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
                        "scroll_horizontal": False,
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
        "rendered_at": "2026-08-27T12:00:00Z",
    },
]
