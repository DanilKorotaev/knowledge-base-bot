"""Ingress orchestrator: parse agent decision and re-route events."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.constants import MessageRole
from utils.db_helpers import get_db

from kb_app_api.ingress import store

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT_PROFILE = "ingress_orchestrator"

ORCHESTRATOR_DECISION_INSTRUCTIONS = (
    "You are the Ingress Orchestrator for this user. You only route events — "
    "do not fix CI, parse receipts, or edit domain vault files yourself.\n"
    "Read the latest external message in this session.\n"
    "End your reply with ONE JSON object (optionally in a ```json fence) using exactly "
    "one of these shapes:\n"
    '1) {"session_id": <int>, "policy": "ingest_only"|"enqueue_agent", "reason": "..."}\n'
    '2) {"session_key": "<binding key>", "policy": "ingest_only"|"enqueue_agent", "reason": "..."}\n'
    '3) {"action": "wait_user", "reason": "..."}\n'
    "If unsure, prefer wait_user and ask the user one short question in the prose above the JSON."
)

_EVENT_ID_RE = re.compile(
    r"External ingress event `([0-9a-fA-F-]{36})`",
)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_event_id_from_prompt(query_text: str) -> str | None:
    m = _EVENT_ID_RE.search(query_text or "")
    return m.group(1) if m else None


def parse_orchestrator_decision(reply_text: str) -> dict[str, Any] | None:
    """Best-effort extract of a routing decision object from assistant prose."""
    text = (reply_text or "").strip()
    if not text:
        return None
    candidates: list[str] = []
    for m in _JSON_FENCE_RE.finditer(text):
        candidates.append(m.group(1))
    start = text.rfind("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("action") == "wait_user":
            return {
                "action": "wait_user",
                "reason": str(data.get("reason") or "").strip(),
            }
        policy = str(data.get("policy") or "ingest_only")
        if policy not in ("ingest_only", "enqueue_agent"):
            policy = "ingest_only"
        if data.get("session_id") is not None or data.get("session_key"):
            out: dict[str, Any] = {
                "policy": policy,
                "reason": str(data.get("reason") or "").strip(),
            }
            if data.get("session_id") is not None:
                out["session_id"] = data["session_id"]
            if data.get("session_key"):
                out["session_key"] = str(data["session_key"]).strip()
            return out
    return None


async def apply_orchestrator_decision(
    *,
    user_id: int,
    orchestrator_session_id: int,
    event_id: str,
    decision: dict[str, Any],
    token_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Re-deliver the original event into the chosen session.
    Anti-loop: never enqueue_agent back into the orchestrator session.
    """
    from kb_app_api.ingress.deliver import post_external_message

    event = await store.get_event(event_id)
    if not event:
        return {"ok": False, "error": "event_not_found"}
    if int(event["user_id"]) != int(user_id):
        return {"ok": False, "error": "event_user_mismatch"}

    if decision.get("action") == "wait_user":
        await store.update_event_status(
            event_id,
            status="routed",
            result={
                **(event.get("result") or {}),
                "orchestrator": {
                    "action": "wait_user",
                    "reason": decision.get("reason") or "",
                    "orchestrator_session_id": orchestrator_session_id,
                },
            },
        )
        return {"ok": True, "action": "wait_user"}

    target_id: int | None = None
    if decision.get("session_id") is not None:
        try:
            target_id = int(decision["session_id"])
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid_session_id"}
    elif decision.get("session_key"):
        target_id = await store.resolve_binding(user_id, str(decision["session_key"]))
        if target_id is None:
            return {"ok": False, "error": "unknown_session_key"}

    if target_id is None:
        return {"ok": False, "error": "no_target"}

    policy = str(decision.get("policy") or "ingest_only")
    if target_id == int(orchestrator_session_id) and policy == "enqueue_agent":
        policy = "ingest_only"

    envelope = dict(event.get("envelope") or {})
    if not envelope:
        envelope = {
            "source": event.get("source") or "",
            "type": event.get("type") or "",
            "summary": event.get("summary") or "External event",
            "detail": None,
            "hints": {},
            "payload": {},
            "links": [],
        }

    fanout_event = {
        **event,
        "id": f"{event_id}:route",
        "summary": event.get("summary") or envelope.get("summary") or "External event",
    }
    token = token_snapshot or {
        "user_id": user_id,
        "channel_id": event.get("channel_id") or "default",
        "adapter_key": event.get("adapter_key"),
        "allow_enqueue_agent": True,
        "agent_runtime": "host",
        "agent_prompt_profile": "untrusted_ingress",
    }

    result = await post_external_message(
        user_id=user_id,
        session_id=target_id,
        event=fanout_event,
        envelope=envelope,
        token=token,
        policy=policy,
        agent_runtime=str(token.get("agent_runtime") or "host"),
        agent_prompt_profile="untrusted_ingress",
    )

    db = await get_db()
    reason = str(decision.get("reason") or "").strip()
    note = (
        f"Маршрут: событие `{event_id}` → сессия `{target_id}` "
        f"(policy={policy})."
    )
    if reason:
        note += f"\nПричина: {reason}"
    await db.add_message(
        orchestrator_session_id,
        str(MessageRole.ASSISTANT),
        note,
        client_message_id=f"ingress-route-note:{event_id}:{target_id}",
    )

    await store.update_event_status(
        event_id,
        status="routed",
        result={
            **(event.get("result") or {}),
            "orchestrator": {
                "action": "routed",
                "target_session_id": target_id,
                "policy": policy,
                "reason": reason,
                "fanout": result,
                "orchestrator_session_id": orchestrator_session_id,
            },
        },
    )
    return {"ok": True, "action": "routed", "target_session_id": target_id, "result": result}


async def maybe_apply_orchestrator_route_after_job(
    *,
    job_query_text: str,
    session_id: int,
    user_id: int,
    reply_text: str,
) -> dict[str, Any] | None:
    """Hook for query worker: if this was an orchestrator ingress job, apply JSON decision."""
    if "You are the Ingress Orchestrator" not in (job_query_text or ""):
        return None
    event_id = extract_event_id_from_prompt(job_query_text)
    if not event_id:
        return None

    orch_binding = await store.resolve_binding(user_id, "orchestrator")
    if orch_binding is not None and int(orch_binding) != int(session_id):
        return None

    decision = parse_orchestrator_decision(reply_text)
    if not decision:
        logger.info(
            "orchestrator reply had no decision JSON event=%s session=%s",
            event_id,
            session_id,
        )
        return {"ok": False, "error": "no_decision_json", "event_id": event_id}

    try:
        return await apply_orchestrator_decision(
            user_id=user_id,
            orchestrator_session_id=int(session_id),
            event_id=event_id,
            decision=decision,
        )
    except Exception:
        logger.exception(
            "orchestrator apply failed event=%s session=%s",
            event_id,
            session_id,
        )
        return {"ok": False, "error": "apply_failed", "event_id": event_id}
