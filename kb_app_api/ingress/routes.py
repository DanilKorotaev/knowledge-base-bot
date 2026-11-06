"""HTTP routes: public POST /api/ingress/{token} + authenticated management."""
from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.ingress import store
from kb_app_api.ingress.deliver import process_event
from kb_app_api.ingress.schema import ensure_ingress_schema
from kb_app_api.timefmt import to_iso_z

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingress"])

_MAX_BODY_BYTES = 2_000_000


class CreateTokenBody(BaseModel):
    label: str = ""
    channel_id: str = "default"
    adapter_key: str | None = None
    allowed_sources: list[str] | None = None
    allow_enqueue_agent: bool = False
    allow_script: bool = False
    agent_runtime: str = "none"
    agent_prompt_profile: str = "untrusted_ingress"


class AdapterBody(BaseModel):
    key: str
    label: str = ""
    participant_key: str | None = None
    avatar_asset_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class BindingBody(BaseModel):
    binding_key: str
    session_id: int


class RuleBody(BaseModel):
    match: dict[str, Any] = Field(default_factory=dict)
    extract: dict[str, Any] = Field(default_factory=dict)
    action: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    label: str = ""
    enabled: bool = True


class ScriptBody(BaseModel):
    key: str
    label: str = ""
    command: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


def _public_token(row: dict[str, Any], *, raw: str | None = None) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "label": row.get("label") or "",
        "channel_id": row.get("channel_id") or "default",
        "adapter_key": row.get("adapter_key"),
        "allowed_sources": row.get("allowed_sources"),
        "allow_enqueue_agent": bool(row.get("allow_enqueue_agent")),
        "allow_script": bool(row.get("allow_script")),
        "agent_runtime": row.get("agent_runtime") or "none",
        "agent_prompt_profile": row.get("agent_prompt_profile") or "untrusted_ingress",
        "token_prefix": row.get("token_prefix") or "",
        "revoked_at": to_iso_z(row["revoked_at"]) if row.get("revoked_at") else None,
        "created_at": to_iso_z(row.get("created_at")),
        "ingress_path": f"/api/ingress/{row.get('token_prefix') or ''}…",
    }
    if raw:
        out["token"] = raw
        out["ingress_path"] = f"/api/ingress/{raw}"
        out["ingress_url_path"] = f"/api/ingress/{raw}"
    return out


def _normalize_envelope(raw: dict[str, Any]) -> dict[str, Any]:
    summary = str(raw.get("summary") or raw.get("title") or "").strip()
    if not summary:
        summary = "External event"
    return {
        "source": str(raw.get("source") or ""),
        "type": str(raw.get("type") or ""),
        "summary": summary,
        "detail": raw.get("detail"),
        "hints": raw.get("hints") if isinstance(raw.get("hints"), dict) else {},
        "payload": raw.get("payload") if raw.get("payload") is not None else {},
        "links": raw.get("links") if isinstance(raw.get("links"), list) else [],
        "dedupe_key": (str(raw["dedupe_key"]).strip() if raw.get("dedupe_key") else None),
        "occurred_at": raw.get("occurred_at"),
        "adapter_key": raw.get("adapter_key"),
    }


@router.post("/ingress/{token}")
async def ingest_event(token: str, request: Request) -> dict[str, Any]:
    """Public per-user ingress. Token in path is enough; body is free-form JSON or multipart."""
    await ensure_ingress_schema()
    resolved = await store.resolve_token(token)
    if not resolved:
        raise APIError("not_found", "Unknown or revoked ingress token", status_code=404)

    content_type = (request.headers.get("content-type") or "").lower()
    envelope_raw: dict[str, Any]
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload_field = form.get("payload") or form.get("json") or "{}"
        if hasattr(payload_field, "read"):
            payload_field = (await payload_field.read()).decode("utf-8", errors="replace")  # type: ignore[union-attr]
        try:
            envelope_raw = json.loads(str(payload_field))
        except json.JSONDecodeError as exc:
            raise APIError("invalid_request", "payload must be JSON", status_code=400) from exc
        if not isinstance(envelope_raw, dict):
            raise APIError("invalid_request", "payload must be a JSON object", status_code=400)
        files_meta: list[dict[str, Any]] = []
        for key, value in form.multi_items():
            if key in ("payload", "json"):
                continue
            if hasattr(value, "filename") and hasattr(value, "read"):
                data = await value.read()  # type: ignore[misc]
                if len(data) > _MAX_BODY_BYTES:
                    raise APIError("invalid_request", "file too large", status_code=413)
                files_meta.append(
                    {
                        "field": key,
                        "filename": getattr(value, "filename", None),
                        "content_type": getattr(value, "content_type", None),
                        "size": len(data),
                        # Bytes are not persisted into DB by default (size audit only).
                    }
                )
        envelope_raw.setdefault("payload", {})
        if isinstance(envelope_raw["payload"], dict):
            envelope_raw["payload"] = {**envelope_raw["payload"], "_files": files_meta}
    else:
        body = await request.body()
        if len(body) > _MAX_BODY_BYTES:
            raise APIError("invalid_request", "body too large", status_code=413)
        if not body.strip():
            envelope_raw = {}
        else:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError as exc:
                raise APIError("invalid_request", "body must be JSON", status_code=400) from exc
            if not isinstance(parsed, dict):
                raise APIError("invalid_request", "body must be a JSON object", status_code=400)
            envelope_raw = parsed

    if resolved.get("adapter_key") and not envelope_raw.get("adapter_key"):
        envelope_raw["adapter_key"] = resolved["adapter_key"]

    allowed = resolved.get("allowed_sources")
    source = str(envelope_raw.get("source") or "")
    if isinstance(allowed, list) and allowed and source not in allowed:
        raise APIError("forbidden", "source not allowed for this token", status_code=403)

    envelope = _normalize_envelope(envelope_raw)
    event, created = await store.insert_event(
        user_id=int(resolved["user_id"]),
        token_id=str(resolved["id"]),
        channel_id=str(resolved.get("channel_id") or "default"),
        adapter_key=resolved.get("adapter_key"),
        source=envelope["source"],
        event_type=envelope["type"],
        summary=envelope["summary"],
        dedupe_key=envelope.get("dedupe_key"),
        envelope=envelope,
    )
    if not created:
        return {
            "ok": True,
            "deduped": True,
            "event_id": event["id"],
            "status": event.get("status"),
            "result": event.get("result"),
        }

    routed = await process_event(token=resolved, event=event, envelope=envelope)
    return {
        "ok": bool(routed.get("ok")),
        "deduped": False,
        "event_id": event["id"],
        **routed,
    }


@router.get("/me/ingress/tokens")
async def me_list_tokens(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    rows = await store.list_tokens(int(user["id"]))
    return {"tokens": [_public_token(r) for r in rows]}


@router.post("/me/ingress/tokens")
async def me_create_token(
    body: CreateTokenBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    row, raw = await store.create_token(
        user_id=int(user["id"]),
        label=body.label,
        channel_id=body.channel_id,
        adapter_key=body.adapter_key,
        allowed_sources=body.allowed_sources,
        allow_enqueue_agent=body.allow_enqueue_agent,
        allow_script=body.allow_script,
        agent_runtime=body.agent_runtime,
        agent_prompt_profile=body.agent_prompt_profile,
    )
    return _public_token(row, raw=raw)


@router.post("/me/ingress/tokens/{token_id}/revoke")
async def me_revoke_token(
    token_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    ok = await store.revoke_token(user_id=int(user["id"]), token_id=token_id)
    if not ok:
        raise APIError("not_found", "Token not found", status_code=404)
    return {"ok": True}


@router.get("/me/ingress/adapters")
async def me_list_adapters(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    return {"adapters": await store.list_adapters(int(user["id"]))}


@router.put("/me/ingress/adapters")
async def me_upsert_adapter(
    body: AdapterBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    try:
        adapter = await store.upsert_adapter(
            user_id=int(user["id"]),
            key=body.key,
            label=body.label or body.key,
            participant_key=body.participant_key,
            avatar_asset_id=body.avatar_asset_id,
            config=body.config,
        )
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc
    return {"adapter": adapter}


@router.delete("/me/ingress/adapters/{key}")
async def me_delete_adapter(
    key: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    ok = await store.delete_adapter(user_id=int(user["id"]), key=key)
    if not ok:
        raise APIError("not_found", "Adapter not found", status_code=404)
    return {"ok": True}


@router.get("/me/ingress/bindings")
async def me_list_bindings(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    return {"bindings": await store.list_bindings(int(user["id"]))}


@router.put("/me/ingress/bindings")
async def me_upsert_binding(
    body: BindingBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    session = await db.get_session(body.session_id)
    if not session or int(session.get("user_id") or 0) != int(user["id"]):
        raise APIError("not_found", "Session not found", status_code=404)
    await store.upsert_binding(
        user_id=int(user["id"]),
        binding_key=body.binding_key,
        session_id=body.session_id,
    )
    return {"ok": True, "binding_key": body.binding_key, "session_id": body.session_id}


@router.get("/me/ingress/rules")
async def me_list_rules(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    return {"rules": await store.list_rules(int(user["id"]))}


@router.post("/me/ingress/rules")
async def me_create_rule(
    body: RuleBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    rule = await store.create_rule(
        user_id=int(user["id"]),
        match=body.match,
        extract=body.extract,
        action=body.action,
        priority=body.priority,
        label=body.label,
        enabled=body.enabled,
    )
    return {"rule": rule}


@router.post("/me/ingress/rules/{rule_id}/enabled")
async def me_set_rule_enabled(
    rule_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    enabled: bool = True,
) -> dict[str, Any]:
    ok = await store.set_rule_enabled(
        user_id=int(user["id"]),
        rule_id=rule_id,
        enabled=enabled,
    )
    if not ok:
        raise APIError("not_found", "Rule not found", status_code=404)
    return {"ok": True}


@router.delete("/me/ingress/rules/{rule_id}")
async def me_delete_rule(
    rule_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    ok = await store.delete_rule(user_id=int(user["id"]), rule_id=rule_id)
    if not ok:
        raise APIError("not_found", "Rule not found", status_code=404)
    return {"ok": True}


@router.put("/me/ingress/scripts")
async def me_upsert_script(
    body: ScriptBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    script = await store.upsert_script(
        user_id=int(user["id"]),
        key=body.key,
        label=body.label,
        command=body.command,
        enabled=body.enabled,
    )
    return {"script": script}


@router.get("/me/ingress/events")
async def me_list_events(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    limit: int = 50,
) -> dict[str, Any]:
    events = await store.list_events(int(user["id"]), limit=limit)
    # Redact bulky envelope payloads in list view.
    slim = []
    for event in events:
        item = {
            "id": event["id"],
            "source": event.get("source"),
            "type": event.get("type"),
            "summary": event.get("summary"),
            "status": event.get("status"),
            "channel_id": event.get("channel_id"),
            "adapter_key": event.get("adapter_key"),
            "created_at": to_iso_z(event.get("created_at")),
            "error_message": event.get("error_message"),
        }
        slim.append(item)
    return {"events": slim}


@router.post("/me/ingress/avatars")
async def me_upload_avatar(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    participant_key: Annotated[str, Form()] = "default",
    file: UploadFile = File(...),
) -> dict[str, Any]:
    raw = await file.read()
    try:
        asset = await store.upsert_avatar_asset(
            user_id=int(user["id"]),
            participant_key=participant_key,
            content_type=file.content_type or "image/png",
            file_name=file.filename or "avatar.png",
            data=raw,
        )
    except ValueError as exc:
        raise APIError("invalid_request", str(exc), status_code=400) from exc
    return {"avatar": asset}


@router.get("/ingress/avatars/{asset_id}")
async def get_ingress_avatar(asset_id: str) -> Response:
    """Public by unguessable id so chat clients can cache without auth headers."""
    asset = await store.get_avatar_asset(asset_id)
    if not asset:
        raise APIError("not_found", "Avatar not found", status_code=404)
    return FileResponse(
        path=str(asset["path"]),
        media_type=str(asset["content_type"]),
        filename=str(asset["file_name"]),
    )
