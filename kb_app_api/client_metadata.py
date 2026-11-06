"""Capture optional iOS client version headers for logging and agent env."""

from __future__ import annotations

from typing import Any, Mapping

_HEADER_KEYS = (
    "x-kb-app-version",
    "x-kb-app-build",
    "x-kb-app-platform",
    "x-kb-app-os",
    "x-kb-app-log-session",
    "x-kb-app-timezone",
    "x-kb-app-locale",
    "x-kb-structured-ui",
)

# client_meta header key → env var for cursor-agent subprocess
_META_TO_AGENT_ENV = (
    ("x-kb-app-version", "KB_APP_VERSION"),
    ("x-kb-app-build", "KB_APP_BUILD"),
    ("x-kb-app-platform", "KB_APP_PLATFORM"),
    ("x-kb-app-os", "KB_APP_OS"),
    ("x-kb-app-log-session", "KB_APP_LOG_SESSION"),
    ("x-kb-app-timezone", "KB_CLIENT_TZ"),
    ("x-kb-app-locale", "KB_CLIENT_LOCALE"),
)


def client_meta_from_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Extract known X-KB-App-* headers (keys compared case-insensitively)."""
    lower = {str(key).lower(): str(value).strip() for key, value in headers.items() if value}
    meta: dict[str, str] = {}
    for key in _HEADER_KEYS:
        value = lower.get(key)
        if value:
            meta[key] = value
    ua = lower.get("user-agent")
    if ua:
        meta["user-agent"] = ua
    return meta


def structured_ui_allowed_from_headers(headers: Mapping[str, str]) -> bool:
    """Client preference: X-KB-Structured-UI=1 enables agent-attached panels (default off if missing)."""
    lower = {str(key).lower(): str(value).strip() for key, value in headers.items() if value}
    value = lower.get("x-kb-structured-ui", "").lower()
    return value in ("1", "true", "yes", "on")


def agent_env_from_client_meta(meta: Mapping[str, str] | None) -> dict[str, str]:
    """Map stored/request client_meta keys to KB_* env vars (omit empties)."""
    if not meta:
        return {}
    env: dict[str, str] = {}
    for meta_key, env_key in _META_TO_AGENT_ENV:
        value = str(meta.get(meta_key) or "").strip()
        if value:
            env[env_key] = value
    return env


def build_agent_context(
    *,
    channel: str | None = None,
    user_id: int | str | None = None,
    session_id: int | str | None = None,
    client_meta: Mapping[str, str] | None = None,
    extra: Mapping[str, str] | None = None,
    user: Mapping[str, Any] | None = None,
    agent_root: str | None = None,
) -> dict[str, str]:
    """
    Build env overlay for cursor-agent: channel/session/user + optional iOS client_meta.

    Values are strings only; empty/None omitted. Safe to JSON-serialize onto query jobs.
    Sets ``AGENT_ROOT`` from explicit path, ``user``, or ``user_id`` via vault_paths.
    """
    ctx: dict[str, str] = {}
    if channel:
        normalized = str(channel).strip().lower()
        if normalized in ("ios", "kb_app", "kb-app", "application"):
            normalized = "app"
        if normalized:
            ctx["KB_CHANNEL"] = normalized
    if user_id is not None and str(user_id).strip() != "":
        ctx["KB_USER_ID"] = str(user_id).strip()
    if session_id is not None and str(session_id).strip() != "":
        ctx["KB_SESSION_ID"] = str(session_id).strip()
    ctx.update(agent_env_from_client_meta(client_meta))

    root_text = (agent_root or "").strip()
    if root_text:
        from pathlib import Path

        root_text = str(Path(root_text).expanduser().resolve())
    else:
        try:
            from kb_app_api.vault_paths import resolve_agent_data_root

            user_dict = dict(user) if user is not None else None
            root_text = str(
                resolve_agent_data_root(
                    user_dict,
                    user_id=user_id,
                )
            )
        except Exception:
            root_text = ""
    if root_text:
        ctx["AGENT_ROOT"] = root_text

    if extra:
        for key, value in extra.items():
            text = str(value).strip()
            if key and text:
                ctx[str(key)] = text
    return ctx


def agent_context_to_json(ctx: Mapping[str, str] | None) -> str | None:
    if not ctx:
        return None
    import json

    return json.dumps(dict(ctx), ensure_ascii=False, sort_keys=True)


def agent_context_from_json(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if k and v is not None and str(v).strip()}
    text = str(raw).strip()
    if not text:
        return {}
    import json

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items() if k and v is not None and str(v).strip()}
