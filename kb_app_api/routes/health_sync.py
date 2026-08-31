from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config import config
from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.health_paths import (
    resolve_health_file,
    validate_health_file_path,
    vault_relative_path,
)
from utils.db_helpers import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health/sync", tags=["health-sync"])

MAX_FILES_PER_REQUEST = 100
MAX_FILE_BYTES = 10 * 1024 * 1024


class SyncFileItem(BaseModel):
    path: str = Field(..., description="Path relative to the user's health_data folder")
    content_base64: str = Field(..., description="File body, base64-encoded")


class SyncFilesBody(BaseModel):
    files: list[SyncFileItem] = Field(..., min_length=1, max_length=MAX_FILES_PER_REQUEST)


class SyncFilesResponse(BaseModel):
    written: list[str]
    synced_to_nextcloud: bool


@router.get("/state")
async def get_health_sync_state(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    db = await get_db()
    health_root = await db.get_user_health_data_relative(user["id"])
    state_path = resolve_health_file(config.LOCAL_KB_PATH, health_root, "sync_state.json")
    if not state_path.is_file():
        raise APIError("not_found", "sync_state.json не найден", status_code=404)
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise APIError(
            "invalid_state",
            "sync_state.json повреждён",
            status_code=500,
            detail=str(exc),
        )


@router.post("/files", response_model=SyncFilesResponse)
async def upload_health_sync_files(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: SyncFilesBody,
) -> SyncFilesResponse:
    db = await get_db()
    health_root = await db.get_user_health_data_relative(user["id"])
    written_relative: list[str] = []
    vault_paths: list[str] = []

    for item in body.files:
        try:
            relative_path = validate_health_file_path(item.path)
        except ValueError as exc:
            raise APIError(
                "validation_error",
                "Некорректный путь файла",
                detail=f"{item.path}: {exc}",
            )
        try:
            payload = base64.b64decode(item.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise APIError(
                "validation_error",
                "Некорректный content_base64",
                detail=f"{item.path}: {exc}",
            )
        if len(payload) > MAX_FILE_BYTES:
            raise APIError(
                "validation_error",
                f"Файл слишком большой (>{MAX_FILE_BYTES} bytes)",
                detail=item.path,
            )
        target = resolve_health_file(config.LOCAL_KB_PATH, health_root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        written_relative.append(relative_path)
        vault_paths.append(vault_relative_path(health_root, relative_path))

    synced = False
    try:
        from services.sync_service import SyncService

        sync = SyncService()
        if sync.enabled:
            for vault_path in vault_paths:
                ok = await sync.sync_file(vault_path, direction="to")
                if not ok:
                    logger.warning("Health sync upload to Nextcloud failed for %s", vault_path)
            synced = True
    except Exception:
        logger.exception("Health sync Nextcloud upload failed")
        synced = False

    return SyncFilesResponse(written=written_relative, synced_to_nextcloud=synced)
