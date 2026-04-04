# Связывание HealthData при создании заметки тренировки (Path 2)

**Статус:** Запланировано  
**Приоритет:** Средний  
**Категория:** Feature / интеграция с HealthSync  
**Связь:** план «Apple Health iOS приложение» (раздел «Два пути связывания») — Path 2.

## Контекст

Сейчас **health-sync-api** (контейнер `health-sync-api`) обрабатывает **Path 1**: iOS загрузил JSON → `POST /api/health/sync-complete` → дописывается `health:` в frontmatter и `linked_note` в workout JSON.

**Path 2** (ещё не реализован в боте): пользователь сначала записал **голосовуху** → агент создал заметку `Тренировки/.../YYYY-MM-DD ...md` → **позже** появились файлы `HealthData/workouts/*.json`. Нужно при **появлении/сохранении** заметки тренировки проверить KB и, если есть gym-workout за эту дату, выполнить ту же логику связывания, что и webhook.

## Где искать точки входа в кодовой базе

1. **Запись файлов агентом / Cursor CLI** — итоговое сохранение изменений в KB:
   - `utils/file_helpers.py` — `write_file_content`, создание путей.
   - `handlers/callbacks.py` — откат/применение изменений (см. `write_file_content`).
   - `services/query_processing_service.py` / `services/cursor_cli_service.py` — место, где после успешного ответа агента файлы оказываются на диске в `LOCAL_KB_PATH` (`config.LOCAL_KB_PATH`).

2. **Синхронизация Nextcloud → локальная KB** — после pull новых файлов с сервера (`services/sync_service.py`) — опциональный второй хук: если iOS уже залил JSON, а заметку создали на другом устройстве, связывание может понадобиться и здесь.

3. **Повторное использование логики** — не дублировать правила:
   - Вынести общее из `health-sync-api/app/linking.py` в пакет уровня репозитория (см. отдельную задачу `task-tech-health-linking-shared-python-module.md`) **или** вызывать HTTP `POST /api/health/sync-complete` с телом `{ "date": "...", "files": ["HealthData/workouts/..."] }` на `localhost` из бота (требует токен и запущенный контейнер — хуже для unit-тестов).

## Требования к реализации

- [ ] Определить **один** стабильный хук: «файл `.md` под `Тренировки/` с именем `YYYY-MM-DD *` только что записан».
- [ ] Из пути/имени извлечь дату `yyyy-MM-dd`.
- [ ] Найти в `HealthData/workouts/` JSON с `is_gym: true` и этой датой (как в `linking.process_sync_payload` — список файлов можно собрать локально `glob` / `iterdir`).
- [ ] Вызвать ту же логику, что webhook: frontmatter `health`, поле `linked_note` в JSON.
- [ ] **Идемпотентность:** если `linked_note` уже заполнен — не ломать (как сейчас в API).
- [ ] Логирование: `logger.info` с датой и путями; ошибки не роняют основной поток бота.
- [ ] Тесты: минимум `pytest` с временной KB-директорией (можно переиспользовать сценарии из `health-sync-api/tests/test_linking.py`).

## Критерии готовности

- После сценария «сначала заметка, потом синк HealthSync» (или наоборот) в заметке есть блок `health`, в JSON — `linked_note`, без ручного шага.
- Документация: короткий абзац в `health-sync-api/README.md` или `docs/` про Path 1 vs Path 2.

## Зависимости

- [x] Общий модуль линковки — [`packages/health_linking`](../completed/task-tech-health-linking-shared-python-module.md).
