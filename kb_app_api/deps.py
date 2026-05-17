from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import config
from kb_app_api.errors import APIError

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def require_bearer(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    expected = config.KB_APP_API_TOKEN
    if not expected:
        logger.error("KB_APP_API_TOKEN is not set")
        raise APIError(
            "service_unavailable",
            "KB App API не сконфигурирован",
            status_code=503,
        )
    if creds is None or creds.scheme.lower() != "bearer":
        raise APIError("unauthorized", "Нужен заголовок Authorization: Bearer", status_code=401)
    if creds.credentials != expected:
        raise APIError("forbidden", "Неверный токен", status_code=403)


async def get_api_user(
    request: Request,
    _: Annotated[None, Depends(require_bearer)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    telegram_id = config.KB_APP_API_TELEGRAM_ID
    if request.headers.get("X-KB-App-E2E") == "1":
        telegram_id = config.KB_APP_API_TEST_TELEGRAM_ID

    db = await get_db()
    username = "kb-app-api" if telegram_id == config.KB_APP_API_TELEGRAM_ID else "kb-app-api-e2e"
    user = await db.ensure_user(telegram_id, username)
    if config.ACCESS_MODE == "restricted" and not config.KB_APP_API_BYPASS_ACCESS_CHECK:
        if not user.get("is_allowed"):
            raise APIError(
                "forbidden",
                "В режиме restricted пользователь API не разрешён (is_allowed=false). "
                "Разрешите доступ через бота или задайте KB_APP_API_BYPASS_ACCESS_CHECK=true только для отладки.",
                status_code=403,
            )
    return user
