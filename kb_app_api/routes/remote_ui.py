"""Proxy Structured UI by absolute URL (template/URL come from Actions JSON).

Env only filters **hosts** (and schemes) — no named upstream map:

    REMOTE_UI_HOST_ALLOWLIST=127.0.0.1,localhost,lyrics.coredan.ru

Client (after resolving ``{{q}}`` / ``{{shared_url}}`` in the action URL):

    GET /api/remote-ui?url=http%3A%2F%2F127.0.0.1%3A8095%2Fv1%2Fui%2Fhome
"""

from __future__ import annotations

import logging
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response

from config import config
from kb_app_api.deps import require_bearer
from kb_app_api.errors import APIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remote-ui", tags=["remote-ui"])


def _host_allowed(hostname: str) -> bool:
    allow = {h.lower() for h in (config.REMOTE_UI_HOST_ALLOWLIST or []) if h}
    if not allow:
        return False
    host = (hostname or "").strip().lower()
    if not host:
        return False
    # strip IPv6 brackets
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host in allow


def _validate_target(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise APIError("bad_request", "Missing url query parameter", status_code=400)
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    allowed_schemes = {
        s.lower() for s in (config.REMOTE_UI_ALLOWED_SCHEMES or ["http", "https"]) if s
    }
    if scheme not in allowed_schemes:
        raise APIError(
            "bad_request",
            f"URL scheme not allowed (need one of {sorted(allowed_schemes)})",
            status_code=400,
        )
    if not parsed.hostname:
        raise APIError("bad_request", "URL must include a host", status_code=400)
    if parsed.username or parsed.password:
        raise APIError("bad_request", "URL must not include credentials", status_code=400)
    if not _host_allowed(parsed.hostname):
        raise APIError(
            "forbidden",
            "Host is not in REMOTE_UI_HOST_ALLOWLIST",
            status_code=403,
        )
    return raw


async def _forward(method: str, target: str, request: Request) -> Response:
    timeout = float(config.REMOTE_UI_TIMEOUT_SEC or 12)
    max_bytes = int(config.REMOTE_UI_MAX_BYTES or 512 * 1024)
    headers = {
        "Accept": "application/json",
        "User-Agent": "kb-app-api-remote-ui/1",
    }
    body: bytes | None = None
    if method == "POST":
        body = await request.body()
        if len(body) > max_bytes:
            raise APIError("bad_request", "Request body too large", status_code=413)
        ctype = request.headers.get("content-type")
        if ctype:
            headers["Content-Type"] = ctype

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            upstream_resp = await client.request(
                method,
                target,
                content=body,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.warning("remote-ui timeout url=%s err=%s", target, exc)
        raise APIError("upstream_timeout", "Remote UI timed out", status_code=504) from exc
    except httpx.HTTPError as exc:
        logger.warning("remote-ui fetch failed url=%s err=%s", target, exc)
        raise APIError("upstream_error", "Remote UI fetch failed", status_code=502) from exc

    content = upstream_resp.content
    if len(content) > max_bytes:
        raise APIError("upstream_error", "Remote UI response too large", status_code=502)

    media = upstream_resp.headers.get("content-type", "application/json")
    return Response(
        content=content,
        status_code=upstream_resp.status_code,
        media_type=media.split(";")[0].strip() or "application/json",
    )


@router.get("")
async def proxy_remote_ui_get(
    request: Request,
    _: Annotated[None, Depends(require_bearer)],
    url: str = Query(..., description="Absolute URL to fetch (allowlisted host)"),
) -> Response:
    """Fetch Structured UI JSON from an absolute URL (host must be allowlisted)."""
    target = _validate_target(url)
    # Always GET the target document; Actions templates are resolved on the client.
    return await _forward("GET", target, request)


@router.get("/allowlist")
async def list_allowlist(_: Annotated[None, Depends(require_bearer)]) -> dict[str, Any]:
    """Hosts the proxy will fetch (no secrets)."""
    return {
        "hosts": sorted(config.REMOTE_UI_HOST_ALLOWLIST or []),
        "schemes": sorted(config.REMOTE_UI_ALLOWED_SCHEMES or []),
    }
