"""Связывание HealthData/workouts с заметками Тренировки/ (общий код для API и бота)."""

from .linking import (
    LinkResult,
    LinkingPaths,
    backfill_all_linkable_workouts,
    find_workout_note,
    linkable_workout_path_for_date,
    process_sync_payload,
    workout_json_rel_paths_for_date,
)

__all__ = [
    "LinkResult",
    "LinkingPaths",
    "backfill_all_linkable_workouts",
    "find_workout_note",
    "linkable_workout_path_for_date",
    "process_sync_payload",
    "workout_json_rel_paths_for_date",
]
