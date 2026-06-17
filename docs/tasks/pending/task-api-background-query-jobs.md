# KB App API: фоновые jobs для Cursor-запросов (без привязки к числу uvicorn workers)

**Статус:** 📋 Запланировано  
**Приоритет:** 🔴 Высокий (стабильность API при параллельных чатах)  
**Категория:** KB App API / архитектура  
**Связи:** iOS [task-feature-push-notifications-chat.md](../../../knowledge-base-app-ios/docs/tasks/pending/task-feature-push-notifications-chat.md), [task-ux-chat-streaming-feedback.md](../../../knowledge-base-app-ios/docs/tasks/completed/task-ux-chat-streaming-feedback.md), interim: `scripts/start-kb-app-api-host.sh` (`KB_APP_API_WORKERS=2`)

## Проблема (корневая причина)

Сейчас тяжёлая обработка **живёт внутри HTTP-процесса uvicorn**:

```
POST /sessions/{id}/messages[|/voice|/compose]
  → await QueryProcessingService.process_query_for_api()
       → AUTO_SYNC (до ~5–10 с, 7k+ файлов)
       → Cursor CLI (30–600 с)
       → add_message, push, voice attach, file changes
```

Даже при **обрыве SSE** (`_stream_assistant_sse` → `run_pipeline` в `asyncio.create_task`) задача остаётся в **том же worker-процессе** и на **том же event loop**, что и `GET /sessions`, `/health`.

### Симптомы (наблюдались на prod)

| Симптом | Причина |
|---------|---------|
| Pull-to-refresh списка сессий «висит» 1–2 мин | Worker занят долгим `process_query_for_api` |
| `NSURLErrorDomain -1001` на `/api/sessions` | Тот же worker не отвечает; иногда **весь event loop** блокирован |
| `/health` тоже не отвечает | Не «мало workers», а **заморозка процесса** (sync/долгий await в критическом пути) |
| Зависание после voice + Cursor ~51 с, ответ в БД есть | Pipeline почти завершился, но процесс не вернулся к обслуживанию HTTP |

### Почему «просто добавить workers» — не решение

- `workers=N` → максимум **N** параллельных тяжёлых запросов; 4 чата = нужно угадывать 4.
- Каждый worker — отдельный пул БД, память, in-memory `query_cancel_registry`.
- При блокировке event loop **один** worker «умирает» для всех своих клиентов.

**Цель:** HTTP-слой всегда лёгкий; тяжёлое — в **отдельных job worker-ах**, масштабируемых по очереди, а не по магическому числу uvicorn.

## Целевая архитектура

```mermaid
sequenceDiagram
    participant iOS
    participant API as KB App API (uvicorn)
    participant Q as query_jobs (PostgreSQL)
    participant W as Query worker process
    participant Cursor

    iOS->>API: POST /messages (или SSE)
    API->>API: save user message
    API->>Q: INSERT job status=queued
    API-->>iOS: 202 / SSE processing (+ job_id)
    W->>Q: claim next job
    W->>Cursor: process_query (sync, subprocess)
    W->>Q: status=done, assistant_message_id
    W->>API: optional notify via DB only
  Note over iOS: SSE если на экране; иначе poll GET messages + push
    iOS->>API: GET /sessions, GET /messages
    API-->>iOS: быстрый ответ
```

### Принципы

1. **HTTP handlers** только: auth, validation, запись user message, постановка job, отдача статуса/SSE.
2. **Query worker** — отдельный процесс (`python -m kb_app_api.query_worker` или launchd plist), N воркеров через конфиг **без** изменения uvicorn.
3. **Очередь в PostgreSQL** (таблица `query_jobs`) — переживает рестарт API, видна из любого процесса.
4. **Параллельные сессии** = несколько jobs в статусе `running` (лимит `MAX_CONCURRENT_QUERY_JOBS` в конфиге, не привязан к uvicorn).
5. **Отмена** — через БД (`cancel_requested_at`), worker проверяет и убивает subprocess (расширить `query_cancel_registry` или заменить).

## Модель данных (черновик)

```sql
CREATE TABLE query_jobs (
    id UUID PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL,  -- queued | running | done | failed | cancelled
    query_text TEXT,
    use_knowledge_base BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    assistant_message_id INTEGER REFERENCES messages(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);
CREATE INDEX idx_query_jobs_status_created ON query_jobs(status, created_at);
```

Опционально: JSON `metadata` (voice file path, attachment ids, `telegram_user_id`).

## Изменения API (эволюционно)

### Фаза 1 (минимальный MVP)

- [ ] Таблица `query_jobs` + `QueryJobService` (enqueue, claim, complete, fail).
- [ ] Отдельный **worker process** вызывает существующий `QueryProcessingService.process_query_for_api` (без дублирования логики).
- [ ] `POST …/messages` (non-SSE): **202** `{ "job_id", "status": "queued" }` после сохранения user message; iOS poll `GET …/messages` (уже умеет).
- [ ] SSE: как сейчас `processing`, но pipeline в worker; deltas через **polling job progress** или Redis/pubsub (фаза 1.5 — см. ниже).
- [ ] Launchd: `com.coredan.kb-app-query-worker.plist` на Mac mini.

### Фаза 2 (SSE из worker)

- [ ] Таблица `query_job_chunks` или NOTIFY/LISTEN для стриминга delta в API process.
- [ ] API SSE endpoint подписывается на job_id и проксирует chunks (HTTP остаётся лёгким).

### Фаза 3

- [ ] `DELETE /api/jobs/{id}` — отмена.
- [ ] `GET /api/sessions/{id}/jobs/active` — UI «ассистент думает» без открытого SSE.
- [ ] Per-user fair queue (не более K running jobs на user).

## Что НЕ переносим в HTTP worker

| Операция | Где выполнять |
|----------|----------------|
| Cursor CLI subprocess | Query worker |
| AUTO_SYNC перед запросом | Query worker (или вынести в отдельный cron — отдельная задача) |
| APNs push после ответа | Query worker (или fire-and-forget task в worker) |
| `GET /sessions`, `/health` | Только uvicorn |

## iOS (минимальные доработки)

- Уже есть: poll messages при уходе с экрана, push при готовности.
- Возможно: обрабатывать **202 + job_id** вместо ожидания 201 с полным телом (опционально).
- SSE: без изменений на фазе 2, если прокси из worker.

## Interim (уже сделано)

- `KB_APP_API_WORKERS=2` в `start-kb-app-api-host.sh` — **временная** подушка, не заменяет эту задачу.

## Критерии приёмки

- [ ] 4 параллельных запроса в **разных** session_id: `GET /sessions` и `GET /health` отвечают < 500 ms при занятых jobs.
- [ ] Рестарт uvicorn не убивает running jobs (worker отдельный процесс).
- [ ] После завершения job: assistant message в БД, push уходит (если настроен APNs).
- [ ] Логи: job_id в каждой строке pipeline.

## Оценка

| Блок | Объём |
|------|-------|
| Схема БД + job service | ~0.5–1 д |
| Worker process + launchd | ~1 д |
| Рефактор routes (enqueue вместо await) | ~1–2 д |
| SSE bridge (фаза 2) | ~1–2 д |
| iOS 202/poll (если нужно) | ~0.5 д |

## Альтернативы (отклонены для нашего масштаба)

| Вариант | Почему нет |
|---------|------------|
| Только больше uvicorn workers | Нужно угадывать N; не спасает от block event loop |
| Celery + Redis | Лишняя инфра на одном mini |
| Отдельный сервер для Cursor | Overkill |
| `asyncio.to_thread` для всего Cursor | Лучше чем ничего, но GIL/память и нет персистентной очереди |
