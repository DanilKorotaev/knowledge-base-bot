# TODO

## Выполнено ✅

Все выполненные задачи перенесены в отдельный файл для удобной навигации: [completed.md](completed.md)

## В процессе 🚧

- [🚧] [Интеграция с Cursor CLI](tasks/pending/task-feature-cursor-cli-integration.md) - базовая версия реализована
- [🚧] [Обработка текстовых сообщений](tasks/pending/task-feature-text-messages.md) - минимальная версия реализована

## Запланировано 📋

### Основной функционал

- [x] [Telegram Mini App для управления сессиями](tasks/completed/task-feature-miniapp-sessions.md) ✅
- [ ] [Интеграция с NextCloud](tasks/pending/task-feature-nextcloud-integration.md)
- [ ] [Реализация базовой структуры проекта](tasks/pending/task-setup-project-structure.md) - _перемещено в pending для дальнейшей работы_
- [ ] [Управление сессиями](tasks/pending/task-feature-session-management.md)
- [ ] [Обработка голосовых сообщений](tasks/pending/task-feature-voice-messages.md)
- [ ] [Обработка файлов и фото](tasks/pending/task-feature-media-handling.md)
- [ ] [Поддержка фото/файлов как самостоятельных запросов](tasks/pending/task-feature-photo-only-queries.md)
- [ ] [Отслеживание изменений файлов](tasks/pending/task-feature-change-tracking.md)
- [ ] [Синхронизация с NextCloud](tasks/pending/task-feature-sync-service.md)

### Улучшения UX

- [x] [Исправить отображение путей к файлам в Telegram](tasks/completed/task-ux-fix-file-paths-in-telegram.md) ✅
- [x] [Стриминг ответов Cursor CLI в Telegram](tasks/completed/task-feature-streaming-responses.md) ✅
- [x] [Прямые ссылки на файлы в NextCloud Web UI](tasks/completed/task-feature-nextcloud-web-links.md) ✅
- [ ] [Кликабельные ссылки на файлы в ответах AI](tasks/pending/task-ux-clickable-file-links-in-response.md)
- [ ] [Улучшение интерфейса команд](tasks/pending/task-ux-commands-improvement.md)

### Технические улучшения

- [ ] [Добавить pydantic-based settings для валидации конфигурации](tasks/pending/task-tech-pydantic-settings.md)
- [ ] [Улучшить логирование (структурированные логи)](tasks/pending/task-tech-structured-logging.md)
- [ ] [Внедрение процессов тестирования](tasks/pending/task-testing-implementation.md)
- [ ] [Оптимизация работы с базой знаний](tasks/pending/task-tech-kb-optimization.md)

### Apple Health / HealthSync (сервер)

Задачи для репозитория бота; клиент — iOS [HealthSync](https://github.com/DanilKorotaev/HealthSync).

- [ ] [Path 2: связывание HealthData при сохранении заметки тренировки](tasks/pending/task-feature-bot-health-link-when-note-saved.md)
- [ ] [Общий Python-модуль линковки (DRY с health-sync-api)](tasks/pending/task-tech-health-linking-shared-python-module.md)
- [ ] [Контракт и эксплуатация Health Sync API](tasks/pending/task-tech-health-sync-api-contract.md)

### Интеграции и расширения

- [ ] [Интеграция с Google Calendar](tasks/pending/task-feature-google-calendar-integration.md)
- [ ] [Скачивание видео из различных сервисов](tasks/pending/task-feature-video-download.md)

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

