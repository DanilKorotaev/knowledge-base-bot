"""
Path 2: связывание HealthData с заметкой тренировки при появлении заметки в KB (бот).

Вызывается после записи `.md` и после изменений от Cursor CLI — см. `write_file_content`,
`query_processing_service.handle_file_changes`.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TRAINING_NOTE_NAME = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) .+\.md$",
    re.IGNORECASE,
)


def _enabled() -> bool:
    return os.getenv("HEALTH_LINK_ON_NOTE_WRITE", "true").lower() in ("true", "1", "yes")


def maybe_link_health_after_training_note_saved(absolute_file_path: Path) -> None:
    """Если сохранён файл заметки тренировки — попытаться связать с JSON (при наличии)."""
    if not _enabled():
        return
    try:
        _run_link_for_note_path(absolute_file_path.resolve())
    except Exception as e:
        logger.warning("Health link Path 2 (single file): %s", e, exc_info=True)


def maybe_link_health_for_kb_changes(kb_root: Path, changes: list[dict[str, Any]]) -> None:
    """Обработать список изменений от Cursor CLI (created/modified)."""
    if not _enabled() or not changes:
        return
    kb = Path(kb_root).resolve()
    seen: set[str] = set()
    for ch in changes:
        if ch.get("type") == "deleted":
            continue
        rel = ch.get("path")
        if not rel or not isinstance(rel, str):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        try:
            _run_link_for_note_path((kb / rel).resolve())
        except Exception as e:
            logger.warning("Health link Path 2 (changes %s): %s", rel, e, exc_info=True)


def _run_link_for_note_path(path: Path) -> None:
    from config import config

    from health_linking import DEFAULT_PATHS, process_sync_payload, workout_json_rel_paths_for_date

    if not path.is_file():
        return
    if path.suffix.lower() != ".md":
        return

    kb = Path(config.LOCAL_KB_PATH).resolve()
    try:
        rel = path.resolve().relative_to(kb)
    except ValueError:
        return

    parts = rel.parts
    if len(parts) < 3:
        return
    if parts[0] != DEFAULT_PATHS.training_root:
        return

    m = _TRAINING_NOTE_NAME.match(path.name)
    if not m:
        return
    date_str = m.group("date")

    files = workout_json_rel_paths_for_date(kb, date_str)
    if not files:
        logger.debug("Path 2: нет workout JSON для даты %s", date_str)
        return

    result = process_sync_payload(kb, date_str, files)
    if result.linked:
        logger.info("Path 2 health link: %s", result.linked)
    if result.errors:
        logger.warning("Path 2 health link errors: %s", result.errors)
