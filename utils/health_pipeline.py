"""
Post-sync pipeline: линковка workout JSON ↔ заметки + пересчёт derived.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _enabled_linking() -> bool:
    import os

    return os.getenv("HEALTH_LINK_ON_SYNC", "true").lower() in ("true", "1", "yes")


def _enabled_derived() -> bool:
    import os

    return os.getenv("HEALTH_DERIVED_ON_SYNC", "true").lower() in ("true", "1", "yes")


def run_health_post_sync(
    kb: Path,
    date: str,
    uploaded_files: list[str],
) -> dict[str, object]:
    """
    После загрузки HealthData: связать новые workouts и обновить derived JSON.
    """
    result: dict[str, object] = {"linked": [], "link_skipped": [], "link_errors": []}

    if _enabled_linking():
        try:
            from health_linking import linkable_workout_path_for_date, process_sync_payload

            workout_files = [
                f.replace("\\", "/").lstrip("/")
                for f in uploaded_files
                if f.replace("\\", "/").startswith("HealthData/workouts/")
                and f.endswith(".json")
            ]
            to_link: list[str] = []
            if workout_files:
                to_link = workout_files
            else:
                rel = linkable_workout_path_for_date(kb, date)
                if rel:
                    to_link = [rel]
            if to_link:
                link_result = process_sync_payload(kb, date, to_link)
                result["linked"] = link_result.linked
                result["link_skipped"] = link_result.skipped
                result["link_errors"] = link_result.errors
                if link_result.linked:
                    logger.info("Health post-sync linked: %s", link_result.linked)
        except Exception as e:
            logger.warning("Health post-sync linking failed: %s", e, exc_info=True)
            result["link_errors"] = [str(e)]

    if _enabled_derived():
        try:
            from health_aggregate import refresh_derived

            summary = refresh_derived(kb)
            result["derived_refreshed"] = True
            result["derived_daily_count"] = summary.get("daily_files_count")
        except Exception as e:
            logger.warning("Health derived refresh failed: %s", e, exc_info=True)
            result["derived_refreshed"] = False
            result["derived_error"] = str(e)

    return result
