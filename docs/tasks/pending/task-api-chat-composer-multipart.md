# KB App API: compose message (text + multiple files + voice)

**Status:** In progress (route + tests landed; deploy + contract doc pending)  
**Priority:** High (blocks iOS Telegram-style composer)  
**Category:** KB App API

## Problem

iOS needs to send **one user turn** with optional text, multiple images/files, and one or more voice clips (with transcriptions) → **one** Cursor pipeline run and **one** assistant reply.

Current API:

| Endpoint | Limitation |
|----------|------------|
| `POST …/messages` | Text JSON only |
| `POST …/attachments` | Single `file`; runs pipeline immediately |
| `POST …/messages/voice` | Single `audio` + `content` |

`QueryProcessingService.process_query_for_api` and `CursorCLIService.process_query` already support `attached_files: List[Path]` — HTTP layer does not.

**iOS task:** `knowledge-base-app-ios/docs/tasks/pending/task-ux-chat-composer-telegram.md`  
**Obsidian:** `Документация/Задачи/task-kb-app-chat-composer-telegram-ux.md`

## Proposed endpoint

`POST /api/sessions/{session_id}/messages/compose`

### Request

`multipart/form-data`:

- `content` (optional string) — user text; if empty and files present, use default attach prompt (same as `post_attachment`)
- `use_knowledge_base` (form bool)
- `files` — repeatable file parts (images, documents)
- `audio` — repeatable audio parts (m4a, etc.)
- `audio_transcriptions` (optional) — JSON array of strings, same order as `audio` parts

Header: `Accept: text/event-stream, application/json;q=0.9` — same SSE behavior as `POST …/messages`.

### Server flow

1. `require_session_for_user`
2. Persist user message with `content` (trimmed or default prompt)
3. For each file: save under `.kb_app_api_uploads/{session_id}/`, `db.add_attachment` → **this** `message_id` (photo vs document by mime)
4. For each audio: save path, `add_attachment` voice + store transcription on attachment/message (reuse `voice_attachments` helpers, bound to explicit message_id not “last user in thread”)
5. `process_query_for_api(content, attached_files=all_paths, on_chunk=…)` once
6. Return SSE stream or JSON `{ messages: [...] }`

### Errors

- No content, no files, no audio → `validation_error`
- Empty file → `validation_error`
- Processing failure → `processing_error` (same as existing routes)

## Implementation checklist

- [x] Route in `kb_app_api/routes/messages.py` (or new `compose.py` router)
- [x] Refactor `attach_voice_to_last_user_message` → `attach_voice_to_message(message_id, …)` if needed
- [x] Tests: multipart with 2 files + text; 2 audio + transcriptions; SSE deltas
- [ ] Update `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`
- [ ] OpenAPI snippet if maintained in repo

## Backward compatibility

Keep `POST …/attachments`, `POST …/messages/voice`, `POST …/messages` unchanged for Telegram bot and legacy iOS paths.

## Acceptance

- [ ] One compose request with text + 2 images → single user message, 2 attachments, single assistant reply
- [ ] Compose with 2 audio parts → 2 voice attachments on same user message, transcriptions stored
- [ ] SSE streaming works with `Accept: text/event-stream`
- [ ] Session ownership and auth match existing message routes

## Estimate

~1–2 days including tests and contract update
