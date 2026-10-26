"""Installable board presets (empty Overview/Actions by default)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Built-in catalog — not seeded into DB until the user installs.
BOARD_PRESETS: list[dict[str, Any]] = [
    {
        "id": "active-jobs",
        "title": "Активные запросы",
        "subtitle": "Фоновые Cursor-задачи: статус, отмена",
        "icon": "bolt.horizontal.circle",
        "kind": "system",
        "sort_order": 50,
        "enabled": True,
        "definition": {
            "provider": "system_query_jobs",
            "period_ui": "none",
            "labels": {
                "title": "Активные запросы",
                "empty": "Сейчас нет активных запросов",
                "cancel": "Отменить",
                "list_title": "Запросы",
                "list_subtitle": "Фоновые Cursor-задачи",
                "tip": (
                    "Долгие ответы агента идут здесь. "
                    "Можно отменить, если запрос завис."
                ),
                "col_status": "Статус",
                "col_session": "Сессия",
                "col_started": "Старт",
                "col_elapsed": "В работе",
            },
        },
        "list_cell": {
            "kind": "status",
            "title": "Активные запросы",
            "subtitle": "Фоновые Cursor-задачи",
            "status_text": "—",
            "status_tone": "neutral",
        },
        "surface": "actions",
    },
    {
        "id": "actions-presets",
        "title": "Пресеты",
        "subtitle": "Быстрые действия во вкладке Actions",
        "icon": "rectangle.stack",
        "kind": "system",
        "sort_order": 40,
        "enabled": True,
        "definition": {"provider": "static", "period_ui": "none"},
        "list_cell": {
            "kind": "status",
            "title": "Пресеты",
            "subtitle": "Быстрые действия",
            "status_text": "—",
            "status_tone": "neutral",
        },
        "rendered_document": {
            "schema_version": 1,
            "screen": {
                "type": "vstack",
                "id": "root",
                "children": [
                    {
                        "type": "text",
                        "id": "title",
                        "text": "Пресеты",
                    },
                    {
                        "type": "callout",
                        "id": "hint",
                        "text": (
                            "Здесь будут ваши быстрые действия. "
                            "Пока пусто — добавьте через агента или MCP."
                        ),
                        "variant": "tip",
                    },
                ],
            },
        },
        "surface": "actions",
    },
]


def list_preset_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for preset in BOARD_PRESETS:
        out.append(
            {
                "id": preset["id"],
                "title": preset["title"],
                "subtitle": preset.get("subtitle"),
                "icon": preset.get("icon"),
                "kind": preset.get("kind") or "system",
                "surface": preset.get("surface") or "overview",
            }
        )
    return out


def get_preset(preset_id: str) -> dict[str, Any] | None:
    pid = (preset_id or "").strip()
    for preset in BOARD_PRESETS:
        if preset["id"] == pid:
            return deepcopy(preset)
    return None


def preset_to_board_row(preset: dict[str, Any], *, user_id: int) -> dict[str, Any]:
    row = deepcopy(preset)
    row.pop("surface", None)
    row["user_id"] = int(user_id)
    row["enabled"] = True
    return row
