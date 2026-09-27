"""System board: active Cursor query jobs + cancel buttons."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from kb_app_api.query_jobs.service import QueryJob, QueryJobService

PROVIDER_ID = "system_query_jobs"


def _truncate(text: str, limit: int = 80) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(0, limit - 1)] + "…"


async def compute(
    board_meta: dict[str, Any],
    definition: dict[str, Any],
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    labels = definition.get("labels") or {}
    title = str(labels.get("title") or board_meta.get("title") or board_meta["id"])
    empty = str(labels.get("empty") or "No active jobs")
    cancel_label = str(labels.get("cancel") or "Cancel")
    tip = str(labels.get("tip") or "").strip()

    service = QueryJobService()
    jobs: list[QueryJob] = await service.list_active(user_id=user_id, limit=40)

    children: list[dict[str, Any]] = [
        {"type": "text", "id": "title", "text": title},
    ]
    if tip:
        children.append({"type": "callout", "id": "tip", "text": tip, "variant": "tip"})

    if not jobs:
        children.append({"type": "callout", "id": "empty", "text": empty, "variant": "info"})
    else:
        for job in jobs:
            row_id = f"job_{job.id}"
            preview = _truncate(job.query_text or "(empty)")
            children.append(
                {
                    "type": "vstack",
                    "id": row_id,
                    "spacing": 6,
                    "children": [
                        {
                            "type": "text",
                            "id": f"{row_id}_query",
                            "text": preview,
                        },
                        {
                            "type": "hstack",
                            "id": f"{row_id}_meta",
                            "spacing": 8,
                            "children": [
                                {
                                    "type": "metric",
                                    "id": f"{row_id}_status",
                                    "label": str(labels.get("col_status") or "Status"),
                                    "text": job.status,
                                },
                                {
                                    "type": "metric",
                                    "id": f"{row_id}_session",
                                    "label": str(labels.get("col_session") or "Session"),
                                    "text": str(job.session_id),
                                },
                                {
                                    "type": "button",
                                    "id": job.id,
                                    "label": cancel_label,
                                    "action_id": "cancel_job",
                                },
                            ],
                        },
                    ],
                }
            )

    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    list_cell = {
        "kind": "status",
        "title": str(labels.get("list_title") or title),
        "subtitle": str(labels.get("list_subtitle") or board_meta.get("subtitle") or ""),
        "status": "idle" if not jobs else "running",
        "status_label": empty if not jobs else f"{len(jobs)} active",
    }
    board = {
        "id": board_meta["id"],
        "title": board_meta.get("title") or title,
        "subtitle": board_meta.get("subtitle") or list_cell.get("subtitle"),
        "icon": board_meta.get("icon"),
        "kind": board_meta.get("kind") or "system",
        "sort_order": int(board_meta.get("sort_order") or 0),
        "enabled": bool(board_meta.get("enabled", True)),
        "list_cell": list_cell,
        "rendered_at": rendered_at,
        "period_ui": "none",
    }
    return {
        "board": board,
        "document": {
            "schema_version": 1,
            "screen": {"type": "vstack", "id": "root", "children": children},
        },
        "rendered_at": rendered_at,
        "period": "all",
        "from": None,
        "to": None,
    }
