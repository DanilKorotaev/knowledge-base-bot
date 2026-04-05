from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Ошибка с телом `{"error": {...}}` по контракту KB App API."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail


def error_body(code: str, message: str, detail: str | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "detail": detail,
        }
    }


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.detail),
    )


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    msgs = exc.errors()
    first = msgs[0] if msgs else {}
    loc = ".".join(str(x) for x in first.get("loc", ()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            "validation_error",
            "Некорректные данные запроса",
            detail=f"{loc}: {first.get('msg', '')}" if loc else None,
        ),
    )
