# KB App API + бот: осмысленные заголовки сессий (`display_title`)

**Статус:** 📋 Запланировано  
**Приоритет:** 🟡 Средний  
**Категория:** KB App API / UX  
**Связанные:**

- [task-ux-session-display-title.md](task-ux-session-display-title.md) — исследование и алгоритм для Telegram/Mini App
- [task-api-session-crud-extensions.md](task-api-session-crud-extensions.md) — PATCH для ручного rename
- iOS: [task-feature-session-delete-rename.md](../../../knowledge-base-app-ios/docs/tasks/pending/task-feature-session-delete-rename.md)

## Контекст

- В БД уже есть `sessions.display_title`; KB App API отдаёт его как `title` (`session_to_kb`).
- При создании через API можно передать `title`; если пусто — fallback `Session {id}`.
- В боте запланирована **авто-генерация** короткого заголовка после первого Q&A (LLM через `run_simple_prompt`, fallback — обрезка первого сообщения) — см. `task-ux-session-display-title.md`.

## Цели

1. После первого успешного ответа в сессии (если `display_title IS NULL`) — **один раз** сгенерировать заголовок (общая логика с Telegram-ботом).
2. Экспонировать заголовок во всех KB App API responses (`GET sessions`, `POST session`, messages side-effect не обязателен).
3. PATCH rename не перезаписывается авто-генерацией (флаг `title_locked` или «не NULL после ручной правки» — уточнить при реализации).

## Задачи

- [ ] Вынести генерацию заголовка в сервис (например `SessionTitleService`) — переиспользовать из `QueryProcessingService` для API и бота.
- [ ] Конфиг: `SESSION_TITLE_MODEL` (default = `TRANSCRIPTION_POLISH_MODEL`).
- [ ] Hook после первого assistant message в `QueryProcessingService.process_query_for_api`.
- [ ] Unit-тест: при NULL title после диалога title заполнен; при заданном title — не меняется.
- [ ] Документация: отличие от заголовка вкладки Cursor IDE.

## Acceptance

- [ ] Новая сессия без title после первого диалога получает человекочитаемое имя в списке iOS.
- [ ] Ручной PATCH title сохраняется и не затирается следующими сообщениями.
