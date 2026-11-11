"""User upload of a crashed session log and admin download."""
from __future__ import annotations

import gzip
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from kb_app_api.crash_logs.notify import deliver_log_followup
from kb_app_api.crash_logs.store import (
    MAX_BYTES,
    accept_crash_logs,
    file_path,
    link_for_admin,
    mark_logs_notified,
    save_upload,
    set_accept_crash_logs,
    valid_log_session,
)
from kb_app_api.deps import get_api_user, require_admin
from kb_app_api.errors import APIError

router = APIRouter(tags=["crash-logs"])


class AdminSettingsBody(BaseModel):
    accept_crash_logs: bool | None = None


@router.get("/admin/settings")
async def get_admin_settings(
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, bool]:
    return {"accept_crash_logs": await accept_crash_logs()}


@router.patch("/admin/settings")
async def patch_admin_settings(
    body: AdminSettingsBody,
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, bool]:
    if body.accept_crash_logs is None:
        raise APIError("validation_error", "Нужно передать accept_crash_logs")
    await set_accept_crash_logs(body.accept_crash_logs)
    return {"accept_crash_logs": body.accept_crash_logs}


@router.post("/crash-logs")
async def upload_crash_log(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    log_session: Annotated[str, Form()],
    app_version: Annotated[str, Form()] = "",
    app_build: Annotated[str, Form()] = "",
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not await accept_crash_logs():
        raise APIError(
            "crash_logs_disabled",
            "Приём файлов логов выключен",
            status_code=403,
        )
    session_id = log_session.strip()
    if not valid_log_session(session_id):
        raise APIError("validation_error", "Некорректный log_session")
    payload = await file.read()
    if payload.startswith(b"\x1f\x8b"):
        try:
            payload = gzip.decompress(payload)
        except OSError as exc:
            raise APIError("invalid_request", "Не удалось распаковать gzip", status_code=400) from exc
    if len(payload) > MAX_BYTES * 4:
        raise APIError("invalid_request", "Файл слишком большой", status_code=413)
    row = await save_upload(
        user_id=int(user["id"]),
        log_session=session_id,
        app_version=app_version.strip(),
        app_build=app_build.strip(),
        payload=payload,
    )
    followed = False
    chat_session_id = row.get("chat_session_id")
    if chat_session_id and not int(row.get("logs_notified") or 0):
        result = await deliver_log_followup(
            user_id=int(user["id"]),
            log_session=session_id,
            chat_session_id=int(chat_session_id),
            app_version=str(row.get("app_version") or app_version),
            app_build=str(row.get("app_build") or app_build),
        )
        if result:
            await mark_logs_notified(int(user["id"]), session_id)
            followed = True
    return {"ok": True, "log_session": session_id, "followup": followed}


@router.get("/admin/crash-logs/{log_session}")
async def download_crash_log(
    log_session: str,
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> FileResponse:
    if not valid_log_session(log_session):
        raise APIError("validation_error", "Некорректный log_session")
    row = await link_for_admin(log_session)
    if not row or not row.get("file_name"):
        raise APIError("not_found", "Файл лога не найден", status_code=404)
    path = file_path(int(row["user_id"]), log_session)
    if not path.is_file():
        raise APIError("not_found", "Файл лога не найден", status_code=404)
    return FileResponse(path, media_type="text/plain", filename=f"{log_session}.log")
