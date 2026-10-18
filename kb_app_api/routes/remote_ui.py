"""Generic proxy: named upstream → Structured UI JSON (no domain hardcode).

Env: ``REMOTE_UI_UPSTREAMS=lyrics=http://127.0.0.1:8095``

Client: ``GET /api/remote-ui/lyrics/v1/ui/home`` → ``http://127.0.0.1:8095/v1/ui/home``
"""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, Request, Response

from config import config
from kb_app_api.deps import require_bearer
from kb_app_api.errors import APIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/remote-ui", tags=["remote-ui"])

_UPSTREAM_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def _upstream_base(name: str) -> str:
    key = name.strip().lower()
    if not _UPSTREAM_NAME_RE.match(key):
        raise APIError("bad_request", "Invalid upstream name", status_code=400)
    base = (config.REMOTE_UI_UPSTREAMS or {}).get(key)
    if not base:
        raise APIError(
            "not_found",
            f"Unknown remote-ui upstream: {key}",
            status_code=404,
        )
    return base


@router.api_route(
    "/{upstream}/{path:path}",
    methods=["GET", "POST"],
    dependencies=[Depends(require_bearer)],
)
async def proxy_remote_ui(
    upstream: str,
    path: str,
    request: Request,
) -> Response:
    """Forward to a configured upstream; return JSON body as-is."""
    base = _upstream_base(upstream)
    # urljoin needs trailing slash on base when path has no leading slash handling
    target = urljoin(base.rstrip("/") + "/", path.lstrip("/"))
    if request.url.query:
        target = f"{target}?{request.url.query}"

    timeout = float(config.REMOTE_UI_TIMEOUT_SEC or 12)
    max_bytes = int(config.REMOTE_UI_MAX_BYTES or 512 * 1024)
    headers = {
        "Accept": "application/json",
        "User-Agent": "kb-app-api-remote-ui/1",
    }
    body: bytes | None = None
    if request.method.upper() == "POST":
        body = await request.body()
        if len(body) > max_bytes:
            raise APIError("bad_request", "Request body too large", status_code=413)
        ctype = request.headers.get("content-type")
        if ctype:
            headers["Content-Type"] = ctype

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            upstream_resp = await client.request(
                request.method.upper(),
                target,
                content=body,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.warning("remote-ui timeout upstream=%s err=%s", upstream, exc)
        raise APIError("upstream_timeout", "Remote UI upstream timed out", status_code=504) from exc
    except httpx.HTTPError as exc:
        logger.warning("remote-ui fetch failed upstream=%s err=%s", upstream, exc)
        raise APIError("upstream_error", "Remote UI upstream failed", status_code=502) from exc

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
async def list_upstreams(_: Annotated[None, Depends(require_bearer)]) -> dict[str, Any]:
    """List configured upstream names (no base URLs — avoid leaking internals)."""
    names = sorted((config.REMOTE_UI_UPSTREAMS or {}).keys())
    return {"upstreams": names}
