# `health_linking`

Общая логика связывания `HealthData/workouts/*.json` с заметками `Тренировки/ГГГГ/<Месяц>/` (frontmatter `health`, поле `linked_note` в JSON).

Используется:

- контейнером **`health-sync-api`** (webhook от iOS);
- в перспективе — **ботом** (Path 2: заметка создана раньше JSON), см. `docs/tasks/pending/task-feature-bot-health-link-when-note-saved.md`.

## Импорт

```python
from health_linking import process_sync_payload, find_workout_note, LinkingPaths
```

Пути по умолчанию задаёт `LinkingPaths()`; при необходимости передайте свой экземпляр в `process_sync_payload(..., paths=...)`.

## Зависимости

`python-frontmatter`, `PyYAML` (как в `health-sync-api/requirements.txt`).
