from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response, StreamingResponse

from config import config
from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.serializers import _ATTACHMENT_MIME
from kb_app_api.session_access import parse_session_id, require_session_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["attachments"])

_MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024


def _content_type_for_attachment(att: dict[str, Any], file_path: str | None = None) -> str:
    name = att.get("file_name") or file_path or ""
    guessed, _ = mimetypes.guess_type(name)
    if guessed:
        return guessed
    ftype = att.get("file_type") or ""
    return _ATTACHMENT_MIME.get(str(ftype), "application/octet-stream")


def _local_attachment_path(att: dict[str, Any]) -> Path | None:
    raw = att.get("file_path")
    if not raw:
        return None
    path = Path(str(raw))
    if not path.is_file():
        return None
    return path


@router.get("/{session_id}/attachments/{attachment_id}/file", response_model=None)
async def get_attachment_file(
    session_id: str,
    attachment_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> Response:
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    try:
        aid = int(attachment_id)
        if aid < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise APIError("validation_error", "Некорректный attachment_id", detail=attachment_id)

    from utils.db_helpers import get_db

    db = await get_db()
    attachments = await db.get_session_attachments(sid)
    target = next((a for a in attachments if int(a["id"]) == aid), None)
    if not target:
        raise APIError("not_found", "Вложение не найдено", status_code=404)

    file_name = target.get("file_name") or f"attachment_{aid}"
    local = _local_attachment_path(target)
    if local is not None:
        size = local.stat().st_size
        if size > _MAX_ATTACHMENT_BYTES:
            raise APIError("validation_error", "Файл слишком большой", status_code=413)
        content_type = _content_type_for_attachment(target, str(local))
        return FileResponse(
            path=local,
            media_type=content_type,
            filename=file_name,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    file_id = target.get("file_id")
    if not file_id:
        raise APIError("not_found", "Файл недоступен", status_code=404)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/getFile",
                params={"file_id": file_id},
            )
            data = resp.json()
            if not data.get("ok"):
                raise APIError("not_found", "Файл недоступен в Telegram", status_code=404)

            tg_file_path = data["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{config.TELEGRAM_TOKEN}/{tg_file_path}"
            tg_resp = await client.get(file_url)
            if tg_resp.status_code != 200:
                raise APIError("not_found", "Не удалось скачать файл", status_code=404)

            content = tg_resp.content
            if len(content) > _MAX_ATTACHMENT_BYTES:
                raise APIError("validation_error", "Файл слишком большой", status_code=413)

            content_type = _content_type_for_attachment(target, tg_file_path)
            return StreamingResponse(
                iter([content]),
                media_type=content_type,
                headers={
                    "Content-Disposition": f'inline; filename="{file_name}"',
                    "Cache-Control": "public, max-age=3600",
                },
            )
    except APIError:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки вложения %s: %s", aid, e)
        raise APIError("processing_error", "Ошибка загрузки файла", status_code=500) from e
