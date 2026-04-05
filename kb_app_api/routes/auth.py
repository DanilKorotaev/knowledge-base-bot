"""
Опциональная выдача Bearer-токена для клиента (включается конфигом).

Пока секреты только из окружения — см. kb-app-api/env.example.
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from config import config
from kb_app_api.errors import APIError

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenIssueBody(BaseModel):
    """Тело для обмена на access_token (если на сервере задан KB_APP_API_TOKEN_ISSUE_SECRET)."""

    secret: str = Field(..., min_length=1, description="Секрет выдачи токена (как в KB_APP_API_TOKEN_ISSUE_SECRET)")


@router.post("/token")
async def issue_token(
    body: Annotated[TokenIssueBody | None, Body(default=None)] = None,
) -> dict[str, Any]:
    """
    Включите `KB_APP_API_TOKEN_ENDPOINT_ENABLED=true` и задайте `KB_APP_API_TOKEN` + `KB_APP_API_TOKEN_ISSUE_SECRET`.
    Клиент отправляет тот же секрет в JSON — получает `access_token` для заголовка Authorization.
    """
    if not config.KB_APP_API_TOKEN_ENDPOINT_ENABLED:
        raise APIError(
            "not_found",
            "Эндпоинт выдачи токена отключён",
            status_code=404,
        )

    expected = (config.KB_APP_API_TOKEN_ISSUE_SECRET or "").strip()
    if not expected:
        raise APIError(
            "service_unavailable",
            "На сервере не задан KB_APP_API_TOKEN_ISSUE_SECRET",
            status_code=503,
        )

    if body is None:
        raise APIError(
            "validation_error",
            "Нужен JSON с полем secret",
            detail="body",
            status_code=422,
        )

    if body.secret != expected:
        raise APIError("unauthorized", "Неверный секрет", status_code=401)

    token = (config.KB_APP_API_TOKEN or "").strip()
    if not token:
        raise APIError(
            "service_unavailable",
            "На сервере не задан KB_APP_API_TOKEN",
            status_code=503,
        )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": None,
    }
