# API: ранний ack compose/messages + `client_message_id` (без потери данных на клиенте)

**Статус:** 📋 Запланировано  
**Приоритет:** 🔴 Высокий (парно с iOS outbox)  
**Категория:** KB App API / надёжность доставки  
**Инцидент:** 2026-09-11 session 29 — клиент мог показать waiting, сервер `compose` не видел; draft на iOS очистился.  
**iOS (парная задача):** `knowledge-base-app-ios/docs/tasks/pending/task-bug-chat-send-outbox-optimistic-merge.md`  
**Связано:** `task-api-background-query-jobs.md` (долгий Cursor вне HTTP), `bug-agent-restart-api-mid-reply.md`

## Проблема

Сейчас клиент узнаёт, что user message «принят», только косвенно (SSE пошёл / poll увидел сообщение). Если multipart оборвался **до** `add_message`, на сервере пусто, а iOS уже мог стереть draft.

Compose уже пишет user message **до** Cursor — этого мало без явного контракта id и идемпотентности для retry.

## Цель

1. Клиент передаёт стабильный `client_message_id` (UUID) на `POST …/messages`, `…/voice`, `…/compose`.
2. API сразу после persist user (+ attachments) возвращает/эмитит ack: `{ message_id, client_message_id }` — **до** долгого Cursor (в SSE — отдельное event; в JSON — в ответе когда без stream).
3. Повтор с тем же `client_message_id` в той же session → **не** дублировать user message; вернуть существующий id / продолжить тот же job если есть.
4. Не писать текст голосовых в логи; для ops — только ids и статусы.

## План работ (backend)

### P0 — контракт ack

- [ ] Form/header/JSON field `client_message_id` (optional → потом required с новой версии клиента).
- [ ] Таблица или уникальный индекс `(session_id, client_message_id)` где не null.
- [ ] SSE: event `user_message_acked` (или расширить существующий bootstrap) сразу после `add_message` + persist uploads, **до** `process_query`.
- [ ] Идемпотентный replay: второй POST с тем же id → 200 + тот же `message_id`, без второго user row.
- [ ] Тесты: compose text+audio; duplicate client_message_id; ack до mock Cursor.

### P1 — согласование с jobs

- [ ] Когда появится `task-api-background-query-jobs`: ack = «ingest accepted»; job id отдельно; клиентский outbox переходит `acked` по message_id, ответ ждёт job/SSE/push.
- [ ] Документировать в OpenAPI / integration-notes.

### Не делать

- [ ] Не складывать полный transcript в server logs «для recovery».
- [ ] Не держать вечные копии outbox на сервере сверх обычных `messages`/`attachments`/`transcriptions`.

## Acceptance

- [ ] iOS с outbox может retry тем же `client_message_id` без дубля в ленте.
- [ ] Клиент может clear draft сразу после ack event, не дожидаясь конца Cursor.
- [ ] Unit/API tests зелёные; ручной прогон с TestFlight после iOS P0/P1.

## Файлы (ориентир)

- `kb_app_api/routes/messages.py` (`post_compose_message`, text/voice)
- `database/` (миграция уникальности client_message_id)
- `kb_app_api/tests/test_compose.py` (+ новые)
- docs: `Документация/Задачи/KB App API — бэкенд для iOS/integration-notes.md` (vault)
