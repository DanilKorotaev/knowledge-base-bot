# Общий Python-модуль линковки HealthData ↔ заметки

**Статус:** Запланировано  
**Приоритет:** Средний  
**Категория:** Tech / DRY

## Проблема

Логика в `health-sync-api/app/linking.py` (поиск заметки в `Тренировки/ГГГГ/<Месяц>/`, merge `health` в frontmatter, запись `linked_note`) понадобится в **боте** для Path 2 (`task-feature-bot-health-link-on-note-saved.md`). Дублирование приведёт к расхождению при правках.

## Предлагаемая структура

```
knowledge-base-bot/
  packages/health_linking/   # или health_sync_linking/
    pyproject.toml / setup.cfg (optional, можно без пакета — просто пакет в репо)
    health_linking/
      __init__.py
      linking.py      # перенос из health-sync-api/app/linking.py
      config.py       # минимальные константы путей (или параметры функций)
```

- **health-sync-api/Dockerfile**: `COPY` пакет и `PYTHONPATH`, либо `pip install -e ../packages/health_linking`.
- **bot**: `from health_linking import process_sync_payload` (или узкая функция `link_workouts_for_date(kb, date)`).

## Задачи

- [ ] Вынести код без изменения поведения; прогнать существующие тесты `health-sync-api/tests/`.
- [ ] Обновить импорты в `health-sync-api/app/main.py`.
- [ ] Зафиксировать в `requirements.txt` health-sync-api путь к пакету (editable install) или monorepo layout в Docker build context.

## Критерии готовности

- Один источник истины для линковки; тесты зелёные; образ `health-sync-api` собирается.
