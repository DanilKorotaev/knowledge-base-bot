"""Authenticated notification inbox API."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.notifications import store
from kb_app_api.notifications.schema import ensure_notifications_schema

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


def _public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "source_key": row.get("source_key"),
        "session_id": row.get("session_id"),
        "message_id": row.get("message_id"),
        "event_id": row.get("event_id"),
        "payload": row.get("payload") or {},
        "created_at": row.get("created_at"),
        "read_at": row.get("read_at"),
        "unread": row.get("read_at") is None,
    }


@router.get("")
async def list_my_notifications(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    limit: int = Query(50, ge=1, le=100),
    before: str | None = Query(None),
) -> dict[str, Any]:
    await ensure_notifications_schema()
    uid = int(user["id"])
    rows = await store.list_notifications(uid, limit=limit, before=before)
    unread = await store.unread_count(uid)
    return {
        "notifications": [_public(r) for r in rows],
        "unread_count": unread,
    }


@router.get("/unread-count")
async def my_unread_count(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    await ensure_notifications_schema()
    return {"unread_count": await store.unread_count(int(user["id"]))}


@router.post("/read-all")
async def mark_all_notifications_read(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    await ensure_notifications_schema()
    updated = await store.mark_all_read(int(user["id"]))
    return {"ok": True, "updated": updated, "unread_count": 0}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    await ensure_notifications_schema()
    ok = await store.mark_read(int(user["id"]), notification_id)
    if not ok:
        raise APIError("not_found", "Notification not found", status_code=404)
    return {"ok": True, "unread_count": await store.unread_count(int(user["id"]))}
