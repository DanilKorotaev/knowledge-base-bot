"""Связывание HealthData/workouts с заметками Тренировки/ (общий код для API и бота)."""

from .linking import (
    LinkResult,
    LinkingPaths,
    find_workout_note,
    process_sync_payload,
    workout_json_rel_paths_for_date,
)

__all__ = [
    "LinkResult",
    "LinkingPaths",
    "find_workout_note",
    "process_sync_payload",
    "workout_json_rel_paths_for_date",
]
