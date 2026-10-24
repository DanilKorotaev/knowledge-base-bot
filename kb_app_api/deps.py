from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import config
from kb_app_api.errors import APIError
from kb_app_api.jwt_tokens import decode_access_token
from kb_app_api.vault_paths import absolute_vault_root, ensure_vault_dir

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_api_user_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> Optional[dict[str, Any]]:
    if creds is None or creds.scheme.lower() != "bearer":
        return None
    try:
        return await _user_from_access_token(creds.credentials)
    except APIError:
        return None


async def get_api_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    if creds is None or creds.scheme.lower() != "bearer":
        raise APIError(
            "unauthorized",
            "Нужен заголовок Authorization: Bearer <access_token>",
            status_code=401,
        )
    return await _user_from_access_token(creds.credentials)


async def _user_from_access_token(token: str) -> dict[str, Any]:
    from utils.db_helpers import get_db

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError as exc:
        raise APIError("unauthorized", "Access token истёк", status_code=401) from exc
    except jwt.InvalidTokenError as exc:
        raise APIError("unauthorized", "Неверный access token", status_code=401) from exc

    if payload.get("typ") not in (None, "access"):
        raise APIError("unauthorized", "Неверный тип токена", status_code=401)

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise APIError("unauthorized", "Неверный access token", status_code=401) from exc

    db = await get_db()
    user = await db.get_user_by_id(user_id)
    if not user or not user.get("login"):
        raise APIError("unauthorized", "Пользователь не найден", status_code=401)

    if config.ACCESS_MODE == "restricted" and not user.get("is_allowed"):
        if not config.KB_APP_API_BYPASS_ACCESS_CHECK:
            raise APIError(
                "forbidden",
                "Пользователь не разрешён (is_allowed=false)",
                status_code=403,
            )

    try:
        vault = ensure_vault_dir(user)
        user = dict(user)
        user["vault_root"] = str(vault)
        user["vault_root_absolute"] = str(absolute_vault_root(user))
    except ValueError as exc:
        logger.error("vault resolve failed user=%s: %s", user_id, exc)
        raise APIError("internal_error", "Некорректный vault_root", status_code=500) from exc

    return user


async def require_admin(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    role = (user.get("role") or "").lower()
    if role != "admin" and not user.get("is_admin"):
        raise APIError("forbidden", "Нужны права администратора", status_code=403)
    return user


# Back-compat name used nowhere critical; keep importable
async def require_bearer(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    if creds is None or creds.scheme.lower() != "bearer":
        raise APIError("unauthorized", "Нужен заголовок Authorization: Bearer", status_code=401)
    await _user_from_access_token(creds.credentials)
