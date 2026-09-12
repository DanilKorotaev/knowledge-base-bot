# KB App API: быстрый список сессий (`message_count` без загрузки всех сообщений)

**Статус:** ✅ Выполнено (этап 1 + search, 2026-09-13)  
**Приоритет:** 🟡 Средний (заметно при refresh списка чатов)  
**Категория:** KB App API / производительность БД  
**Связи:** [task-api-background-query-jobs.md](task-api-background-query-jobs.md) (отдельная проблема — блокировка API), iOS `GET /api/sessions` в `URLSessionKnowledgeBaseAPIClient`

## Проблема

`GET /api/sessions` (`kb_app_api/routes/sessions.py`):

```python
raw = await db.get_user_sessions(user["id"], limit=500, ...)
for s in slice_:
    messages = await db.get_session_messages(s["id"])  # ALL messages
    items.append(session_to_kb(s, messages))
```

`session_to_kb` (`serializers.py`) использует:

- `message_count = len(messages)` — нужен только **COUNT**, грузим **все** строки `content`.
- `updated_at = max(m["created_at"])` — при этом `add_message` уже делает `UPDATE sessions SET updated_at = NOW()`.

Тот же антипаттерн в:

- `GET /api/sessions/search`
- `utils/session_helpers.get_user_sessions_for_display` (Telegram/Mini App)
- `miniapp/api/routes.py`

### Симптом

При десятках сессий и сотнях/тысячах сообщений refresh списка в iOS **медленный** (секунды), даже когда API не заблокирован Cursor-запросом.

## Варианты решения

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| **A. SQL `COUNT` одним запросом** | Без миграции; точный count; 1 round-trip | JOIN на каждый list; search всё ещё тяжёлый |
| **B. Денормализация `sessions.message_count`** | O(1) на чтение; быстрее всего для list | Миграция; поддерживать при add/delete message |
| **C. Redis-кэш** | Быстро | Лишний сервис на mini |
| **D. Кэш в памяти API** | Просто | Неверно при 2+ workers; инвалидация |

**Рекомендация:** **B (денормализация)** для prod + **A** как быстрый первый шаг или для сверки.

`updated_at` для списка брать из **`sessions.updated_at`** (уже обновляется в `add_message`), не из max(messages).

## План реализации

### Этап 1 — быстрый win (можно отдельным PR)

- [x] `get_user_sessions_with_counts(user_id, limit, offset)` — один SQL:

```sql
SELECT s.*, COUNT(m.id) AS message_count
FROM sessions s
LEFT JOIN messages m ON m.session_id = s.id
WHERE s.user_id = $1 AND s.status != 'deleted'
GROUP BY s.id
ORDER BY s.updated_at DESC
LIMIT $2
```

- [x] `session_to_kb_from_row(session, message_count)` без загрузки messages.
- [x] Обновить `list_sessions`, `search_sessions` (для search по title — без messages; по тексту — отдельный запрос `EXISTS` / full-text, не грузить все треды).
- [x] Тест: 1 session + 200 messages → list_sessions smoke (`test_sessions_list_performance.py`).

### Этап 2 — денормализация (надёжно)

- [ ] Миграция: `sessions.message_count INTEGER NOT NULL DEFAULT 0`.
- [ ] Backfill: `UPDATE sessions s SET message_count = (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id)`.
- [ ] В `add_message` / delete message / delete session: инкремент/декремент (или пересчёт в транзакции).
- [ ] `list_sessions` читает только `sessions.*`.
- [ ] Опционально: DB trigger как страховка от рассинхрона.

### Этап 3 — search

- [x] Поиск по тексту сообщений: `EXISTS` + join sessions (без загрузки полных тредов).
- [x] Лимит результатов search (limit=100).

## Контракт API

**Без изменений** для iOS: поля `message_count`, `updated_at`, `title` те же (`KB_APP_API_CONTRACT.md`).

## Критерии приёмки

- [x] `GET /api/sessions?per_page=100` не вызывает `get_session_messages` в цикле.
- [ ] При 50 сессиях × 200 сообщений — p95 < 300 ms на mini (локально) — проверить после деплоя.
- [x] `message_count` = `COUNT(*)` через SQL aggregate (этап 2 денормализации ещё нет).
- [x] Mini App / Telegram list helpers используют тот же DB method.

## Не в scope

- Пагинация cursor-based для list (отдельно, если сессий > 500).
- Кэширование на iOS (`PinnedSessionsStore` уже локальный).

## Оценка

| Этап | Объём |
|------|-------|
| 1 — SQL COUNT | ~2–4 ч |
| 2 — денормализация + backfill | ~0.5–1 д |
| 3 — search | ~0.5 д |


## Результат (2026-09-13)

Этап 1 + search без загрузки тредов:

- `get_user_sessions_with_counts` / `count_user_sessions` / `count_session_messages` / `search_user_sessions_with_counts` (Postgres + SQLite)
- `GET /api/sessions` и `/search` — `session_to_kb_from_row`, пагинация через SQL OFFSET
- Mini App + Telegram `get_user_sessions_for_display` на тех же методах
- Этап 2 (денормализация `sessions.message_count`) — по-прежнему опционален
