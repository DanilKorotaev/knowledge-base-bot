"""
Откат записи `file_changes` — та же логика, что в handlers/callbacks.revert_change_callback.
"""
from __future__ import annotations

import logging
from pathlib import Path

from config import config
from kb_app_api.errors import APIError
from services.sync_service import SyncService
from utils.db_helpers import get_db
from utils.file_helpers import write_file_content

logger = logging.getLogger(__name__)


async def revert_file_change_or_raise(change_id: int, user_internal_id: int) -> dict[str, str]:
    """
    Проверяет доступ и откатывает одно изменение на диске + sync в Nextcloud при необходимости.
    """
    db = await get_db()
    change = await db.get_file_change(change_id)
    if not change:
        raise APIError("not_found", "Изменение не найдено", status_code=404)

    session = await db.get_session(change["session_id"])
    if not session or session["user_id"] != user_internal_id:
        raise APIError("forbidden", "Нет доступа к этому изменению", status_code=403)

    rel = change["file_path"]
    file_path = Path(config.LOCAL_KB_PATH) / rel

    try:
        if change["change_type"] == "created":
            if file_path.exists():
                file_path.unlink()
        elif change["change_type"] == "deleted":
            if change["old_content"]:
                write_file_content(file_path, change["old_content"])
        elif change["change_type"] == "modified":
            if change["old_content"] is not None:
                write_file_content(file_path, change["old_content"])
    except Exception as e:
        logger.exception("Ошибка отката файла change_id=%s: %s", change_id, e)
        raise APIError(
            "revert_failed",
            "Не удалось применить откат на диске",
            status_code=500,
            detail=str(e),
        ) from e

    sync_service = SyncService()
    if sync_service.enabled:
        try:
            await sync_service.sync_to_nextcloud()
        except Exception as e:
            logger.warning("Синхронизация после отката: %s", e)

    return {
        "ok": True,
        "change_id": str(change_id),
        "path": rel,
    }
