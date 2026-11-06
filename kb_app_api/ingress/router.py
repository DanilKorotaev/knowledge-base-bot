"""Match ingress rules and decide delivery action."""
from __future__ import annotations

import re
from typing import Any


def _get_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _match_rule(match: dict[str, Any], envelope: dict[str, Any], token: dict[str, Any]) -> bool:
    if not match:
        return True
    source = str(envelope.get("source") or "")
    event_type = str(envelope.get("type") or "")
    channel = str(token.get("channel_id") or "")
    adapter = str(token.get("adapter_key") or envelope.get("adapter_key") or "")

    if "source" in match and str(match["source"]) != source:
        return False
    if "type" in match and str(match["type"]) != event_type:
        return False
    if "channel_id" in match and str(match["channel_id"]) != channel:
        return False
    if "adapter_key" in match and str(match["adapter_key"]) != adapter:
        return False

    # Equality checks on envelope paths: {"equals": {"hints.from_domain": "x"}}
    equals = match.get("equals") or {}
    if isinstance(equals, dict):
        for path, expected in equals.items():
            if _get_path(envelope, str(path)) != expected:
                return False

    # Regex on paths: {"regex": {"hints.commit_message": "KB-Session:\\s*(\\d+)"}}
    # (regex here only gates match; capture groups applied in extract)
    regexes = match.get("regex") or {}
    if isinstance(regexes, dict):
        for path, pattern in regexes.items():
            value = _get_path(envelope, str(path))
            if value is None or re.search(str(pattern), str(value), re.MULTILINE) is None:
                return False

    return True


def apply_extract(extract: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    """Return hints updates from extract config (no personal hardcoded patterns in code)."""
    hints = dict(envelope.get("hints") or {})
    if not extract:
        return hints

    # {"copy": {"session_id": "hints.session_id"}}
    for dest, src in (extract.get("copy") or {}).items():
        value = _get_path(envelope, str(src))
        if value is not None:
            hints[str(dest)] = value

    # {"regex": {"session_id": {"path": "hints.commit_message", "pattern": "..."}}}
    # pattern comes from user rule JSON — agent configures it.
    for dest, spec in (extract.get("regex") or {}).items():
        if not isinstance(spec, dict):
            continue
        path = str(spec.get("path") or "")
        pattern = str(spec.get("pattern") or "")
        group = int(spec.get("group") or 1)
        if not path or not pattern:
            continue
        value = _get_path(envelope, path)
        if value is None:
            continue
        m = re.search(pattern, str(value), re.MULTILINE)
        if m:
            try:
                hints[str(dest)] = m.group(group)
            except IndexError:
                hints[str(dest)] = m.group(0)
    return hints


def select_rule(
    rules: list[dict[str, Any]],
    *,
    envelope: dict[str, Any],
    token: dict[str, Any],
) -> dict[str, Any] | None:
    # Lower priority number wins (1 before 100).
    ordered = sorted(rules, key=lambda r: int(r.get("priority") or 100))
    for rule in ordered:
        if not rule.get("enabled", True):
            continue
        if _match_rule(rule.get("match") or {}, envelope, token):
            return rule
    return None


def resolve_action(
    *,
    rule: dict[str, Any] | None,
    envelope: dict[str, Any],
    token: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalized action:
      kind: session | script | orchestrator | none
      session_id? session_key?
      script_key?
      policy: ingest_only | enqueue_agent
      hints: updated
    """
    hints = dict(envelope.get("hints") or {})
    if rule:
        hints = apply_extract(rule.get("extract") or {}, {**envelope, "hints": hints})
        action = dict(rule.get("action") or {})
    else:
        # No matching rule → AI router session (deliver forces enqueue + orchestrator prompt).
        action = {"kind": "orchestrator", "policy": "enqueue_agent"}

    kind = str(action.get("kind") or "session")
    policy = str(action.get("policy") or "ingest_only")
    if policy not in ("ingest_only", "enqueue_agent"):
        policy = "ingest_only"

    # Token sandbox: cannot escalate beyond token flags.
    if policy == "enqueue_agent" and not token.get("allow_enqueue_agent"):
        policy = "ingest_only"
    if kind == "script" and not token.get("allow_script"):
        kind = "orchestrator"
        policy = "ingest_only"

    # Prefer explicit session_id from action or extracted hints.
    session_id = action.get("session_id") or hints.get("session_id")
    session_key = action.get("session_key")
    script_key = action.get("script_key")

    if kind == "session" and not session_id and not session_key:
        # Fall back to orchestrator when we cannot target a session.
        kind = "orchestrator"

    return {
        "kind": kind,
        "policy": policy,
        "session_id": str(session_id) if session_id is not None else None,
        "session_key": str(session_key) if session_key else None,
        "script_key": str(script_key) if script_key else None,
        "hints": hints,
        "rule_id": rule.get("id") if rule else None,
        "agent_runtime": token.get("agent_runtime") or "none",
        "agent_prompt_profile": token.get("agent_prompt_profile") or "untrusted_ingress",
    }
