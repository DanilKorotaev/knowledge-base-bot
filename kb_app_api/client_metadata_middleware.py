"""ASGI middleware that stores and logs optional iOS client metadata headers."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from kb_app_api.client_metadata import client_meta_from_headers

logger = logging.getLogger("kb_app_api.client_meta")


class ClientMetadataMiddleware(BaseHTTPMiddleware):
    """Attach ``request.state.client_meta`` and log it for mutating API calls."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        meta = client_meta_from_headers(request.headers)
        request.state.client_meta = meta
        if meta and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            path = request.url.path
            if path.startswith("/api/"):
                logger.info(
                    "client_meta method=%s path=%s version=%s build=%s platform=%s os=%s log_session=%s",
                    request.method,
                    path,
                    meta.get("x-kb-app-version", "-"),
                    meta.get("x-kb-app-build", "-"),
                    meta.get("x-kb-app-platform", "-"),
                    meta.get("x-kb-app-os", "-"),
                    meta.get("x-kb-app-log-session", "-"),
                )
        return await call_next(request)
