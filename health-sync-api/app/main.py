"""
Health Sync API — приём webhook от iOS HealthSync после загрузки JSON в Nextcloud.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Корень репозитория knowledge-base-bot при монтировании не нужен — приложение автономно
from health_linking import process_sync_payload

from .config import settings

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Health Sync API",
    description="Связывает HealthData/workouts/*.json с заметками в Тренировки/ после синка",
    version="0.1.0",
)

security = HTTPBearer(auto_error=False)


class SyncCompleteBody(BaseModel):
    """Совпадает с `SyncWebhookPayload` в iOS (HealthSync)."""

    date: str = Field(..., description="Календарная дата синка (yyyy-MM-dd)")
    files: list[str] = Field(default_factory=list, description="Относительные пути внутри базы знаний")


class SyncCompleteResponse(BaseModel):
    ok: bool = True
    date: str
    linked: list[str]
    skipped: list[str]
    errors: list[str]


async def require_bearer(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> None:
    expected = settings.api_token
    if not expected:
        logger.error("HEALTH_SYNC_API_TOKEN is not set")
        raise HTTPException(status_code=503, detail="Health Sync API is not configured")
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    if creds.credentials != expected:
        raise HTTPException(status_code=403, detail="Invalid token")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/health/sync-complete", response_model=SyncCompleteResponse)
async def sync_complete(
    body: SyncCompleteBody,
    _: Annotated[None, Depends(require_bearer)],
) -> SyncCompleteResponse:
    """
    Вызывается приложением после успешной загрузки файлов.
    Связывает `HealthData/workouts/*.json` с заметками по дате для типов из
    `LINKABLE_WORKOUT_TYPES` (по умолчанию `traditional_strength_training`).
    """
    kb = settings.kb_path
    if not kb.is_dir():
        logger.warning("KB path does not exist or is not a directory: %s", kb)
    result = process_sync_payload(kb, body.date, body.files)
    if result.errors:
        logger.warning("sync-complete errors: %s", result.errors)
    return SyncCompleteResponse(
        date=body.date,
        linked=result.linked,
        skipped=result.skipped,
        errors=result.errors,
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8090"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=False)
