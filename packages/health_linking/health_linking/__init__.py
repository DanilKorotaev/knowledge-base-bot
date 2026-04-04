"""Связывание HealthData/workouts с заметками Тренировки/ (общий код для API и бота)."""

from .linking import LinkResult, LinkingPaths, find_workout_note, process_sync_payload

__all__ = [
    "LinkResult",
    "LinkingPaths",
    "find_workout_note",
    "process_sync_payload",
]
