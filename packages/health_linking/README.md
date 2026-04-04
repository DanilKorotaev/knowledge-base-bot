# `health_linking`

Общая логика связывания `HealthData/workouts/*.json` с заметками `Тренировки/ГГГГ/<Месяц>/` (frontmatter `health`, поле `linked_note` в JSON).

Используется:

- контейнером **`health-sync-api`** (Path 1: webhook от iOS);
- **ботом** — Path 2: `utils/health_linking_hook.py` после записи заметки / изменений Cursor CLI.

## Импорт

```python
from health_linking import process_sync_payload, find_workout_note, LinkingPaths
```

Пути по умолчанию задаёт `LinkingPaths()`; при необходимости передайте свой экземпляр в `process_sync_payload(..., paths=...)`.

## Зависимости

`python-frontmatter`, `PyYAML` (как в `health-sync-api/requirements.txt`).
