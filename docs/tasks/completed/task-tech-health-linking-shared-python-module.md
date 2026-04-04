# Общий Python-модуль линковки HealthData ↔ заметки

**Статус:** Done (2026-04-05)  
**Категория:** Tech / DRY

## Результат

- Пакет **`packages/health_linking/health_linking/`** — `process_sync_payload`, `find_workout_note`, `LinkingPaths`, `LinkResult`.
- **`health-sync-api`**: импорт `from health_linking import process_sync_payload`; удалён `app/linking.py`.
- **Docker**: `context: .` в `docker-compose.yml`, `Dockerfile` копирует `packages/health_linking/health_linking` и `health-sync-api/app`.
- Тесты: `health-sync-api/tests/test_linking.py` с `PYTHONPATH=packages/health_linking`.

## Следующий шаг

Бот Path 2: `task-feature-bot-health-link-when-note-saved.md` — подключить тот же пакет.
