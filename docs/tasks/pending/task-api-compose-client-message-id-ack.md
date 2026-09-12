# API: ранний ack compose/messages + `client_message_id` (без потери данных на клиенте)

**Статус:** ✅ P0 реализовано (2026-09-12) — compose Form `client_message_id`, SSE/JSON `user_message_acked`, идемпотентный replay  
**Приоритет:** 🔴 Высокий (парно с iOS outbox)  
**Категория:** KB App API / надёжность доставки  
**Инцидент:** 2026-09-11 session 29 — клиент мог показать waiting, сервер `compose` не видел; draft на iOS очистился.  
**iOS (парная задача):** `knowledge-base-app-ios/docs/tasks/pending/task-bug-chat-send-outbox-optimistic-merge.md`  
**Связано:** `task-api-background-query-jobs.md` (долгий Cursor вне HTTP), `bug-agent-restart-api-mid-reply.md`

## Проблема

Клиент узнавал, что user message «принят», только косвенно. Если multipart оборвался **до** `add_message`, на сервере пусто, а iOS мог стереть draft.

## Цель

1. Клиент передаёт стабильный `client_message_id` на compose (далее — messages/voice).
2. API сразу после persist user (+ attachments) эмитит ack: `{ message_id, client_message_id }` — **до** Cursor.
3. Повтор с тем же `client_message_id` → без дубля user row; skip pipeline если assistant уже есть.
4. Не писать текст голосовых в логи.

## План работ (backend)

### P0 — контракт ack

- [x] Form field `client_message_id` (optional).
- [x] Unique index `(session_id, client_message_id) WHERE NOT NULL`.
- [x] SSE/JSON `user_message_acked` до `process_query`.
- [x] Идемпотентный replay без второго user row.
- [x] Тесты в `test_compose.py`.

### P1

- [ ] Связка с `task-api-background-query-jobs`.
- [ ] То же на `POST …/messages` и `…/voice`.
- [ ] OpenAPI / integration-notes.

## Acceptance

- [x] Unit/API tests зелёные.
- [ ] Ручной прогон с TestFlight после iOS P0.
