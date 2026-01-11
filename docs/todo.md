# TODO

## Выполнено ✅

Все выполненные задачи перенесены в отдельный файл для удобной навигации: [completed.md](completed.md)

## В процессе 🚧

- [🚧] [Интеграция с Cursor CLI](tasks/pending/task-feature-cursor-cli-integration.md) - базовая версия реализована
- [🚧] [Обработка текстовых сообщений](tasks/pending/task-feature-text-messages.md) - минимальная версия реализована

## Запланировано 📋

### Основной функционал

- [ ] [Интеграция с NextCloud](tasks/pending/task-feature-nextcloud-integration.md)
- [ ] [Реализация базовой структуры проекта](tasks/pending/task-setup-project-structure.md) - _перемещено в pending для дальнейшей работы_
- [ ] [Управление сессиями](tasks/pending/task-feature-session-management.md)
- [ ] [Обработка голосовых сообщений](tasks/pending/task-feature-voice-messages.md)
- [ ] [Обработка файлов и фото](tasks/pending/task-feature-media-handling.md)
- [ ] [Отслеживание изменений файлов](tasks/pending/task-feature-change-tracking.md)
- [ ] [Синхронизация с NextCloud](tasks/pending/task-feature-sync-service.md)

### Улучшения UX

- [ ] [Улучшение интерфейса команд](tasks/pending/task-ux-commands-improvement.md)
- [ ] [Добавление inline-кнопок для быстрых действий](tasks/pending/task-ux-inline-buttons.md)

### Технические улучшения

- [ ] [Добавить pydantic-based settings для валидации конфигурации](tasks/pending/task-tech-pydantic-settings.md)
- [ ] [Улучшить логирование (структурированные логи)](tasks/pending/task-tech-structured-logging.md)
- [ ] [Внедрение процессов тестирования](tasks/pending/task-testing-implementation.md)
- [ ] [Оптимизация работы с базой знаний](tasks/pending/task-tech-kb-optimization.md)

### Документация

- [ ] [Создать API документацию](tasks/pending/task-doc-api-documentation.md)
- [ ] [Создать видео-инструкции](tasks/pending/task-doc-video-tutorials.md)
- [ ] [Дополнительные улучшения документации](tasks/pending/task-doc-improvements.md)

---

## Структура задач

Каждая задача имеет свой файл-артефакт в папке [`docs/tasks/pending/`](tasks/pending/) (для невыполненных задач) или [`docs/tasks/completed/`](tasks/completed/) (для выполненных задач), где хранится:
- Описание задачи
- Проблема/цель
- Декомпозиция на подзадачи
- План реализации
- Чеклист выполнения
- Связанные файлы
- Приоритет и статус

## Организация документации

Документация организована по категориям:
- [`tasks/pending/`](tasks/pending/) - невыполненные задачи
- [`tasks/completed/`](tasks/completed/) - выполненные задачи
- Основная документация в корне `docs/`

