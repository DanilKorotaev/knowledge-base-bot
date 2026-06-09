# KB App API: compose message (text + multiple files + voice)

**Completed:** 2026-06-09  
**Commits:** `c9ba2bf` (compose route), `cddb95a` (ANSI sanitizer for assistant text)

**iOS task:** `knowledge-base-app-ios/docs/tasks/completed/task-ux-chat-composer-telegram.md`  
**Obsidian:** `Документация/Задачи/task-kb-app-chat-composer-telegram-ux.md`

**E2E:** iOS Session 109 on prod — text + 2 images + 3 voice → single user message, 5 attachments, one assistant SSE reply.

## Endpoint

`POST /api/sessions/{session_id}/messages/compose`

### Request

`multipart/form-data`:

- `content` (optional string)
- `use_knowledge_base` (form bool)
- `files[]` — repeatable (images, documents)
- `audio[]` — repeatable (m4a, etc.)
- `audio_transcriptions` — JSON array of strings, same order as `audio`

Header: `Accept: text/event-stream, application/json;q=0.9` — SSE like `POST …/messages`.

## Delivered

- [x] Route in `kb_app_api/routes/messages.py`
- [x] `attach_voice_to_message(message_id, …)` in `voice_attachments.py`
- [x] Tests: `kb_app_api/tests/test_compose.py`
- [x] Deployed on prod; acceptance verified from iOS

## Follow-up

- [ ] Update `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`
- [ ] OpenAPI snippet if maintained in repo

## Backward compatibility

Legacy routes unchanged: `POST …/messages`, `POST …/attachments`, `POST …/messages/voice`.

## Notes

- Cursor pipeline receives `attached_files` (images/docs only); voice clips are DB attachments + text in `content`.
- PTY leak `\u001b[?25h` stripped via `utils/terminal_sanitize.py` before saving assistant messages.
