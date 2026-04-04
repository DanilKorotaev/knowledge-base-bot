# Связывание HealthData при создании заметки тренировки (Path 2)

**Статус:** Done (2026-04-05)  
**Категория:** Feature / HealthSync

## Реализация

- **`utils/health_linking_hook.py`** — после сохранения заметки `Тренировки/.../YYYY-MM-DD *.md` собирает `HealthData/workouts/YYYY-MM-DD_*.json` и вызывает `health_linking.process_sync_payload`.
- **Точки входа:**
  - `write_file_content` — откат/ручная запись (не ломает запись при ошибке хука).
  - `query_processing_service.handle_file_changes` — ответ Cursor CLI с изменениями файлов.
- **Отключение:** `HEALTH_LINK_ON_NOTE_WRITE=false` в `.env`.
- **Пакет:** `workout_json_rel_paths_for_date` в `packages/health_linking`.

## Примечание

Синхронизация Nextcloud → локальная KB не дублирует хук; при появлении JSON только после pull сценарий закрывается повторным сохранением заметки или следующим запросом к агенту.
