# Bug: voice/photo attach after Cursor → wrong message

**Status:** Fixed in code (pending deploy)  
**Priority:** High  
**Category:** Bug, kb-app-api, attachments

## Symptoms (session 241, 2026-09-03)

1. «Проверка» + 2 photos via compose — agent quiet ~10–15 min (Cursor long; Share/SSE may show no activity).
2. Voice «Как-будто у нас что-то пошло не так.» saved as message `1670` **without** voice attachment.
3. Later photo-only compose `1672` («Пользователь прикрепил файл…») got **both** the new photo **and** the previous voice (attachment created ~5 min after the photo).

## Root cause

`POST …/messages/voice` and `POST …/attachments` ran Cursor first, then called `attach_voice_to_last_user_message` / attach-to-last-user. If another user message appeared during the long Cursor run, the media landed on the **newer** message.

Compose path was already correct: create message → attach by `message_id` → `save_user_message=False`.

## Fix

- Persist user message + attachment **before** `process_query_for_api`.
- Pass `save_user_message=False`.
- Regression: `kb_app_api/tests/test_voice_attachment_binding.py`.

## Follow-up

- [ ] Deploy / restart `kb-app-api` (prod + staging).
- [x] One-off DB repair for session 241 attachment `620` → message `1670` (ops).
- [ ] Background query jobs / activity UI for long Cursor (`task-api-background-query-jobs.md`).

## Related: stuck processing on 1675

Voice complaint Cursor (PID 16382) started 00:56; host `kb-app-api` restarted 01:03 → pipeline died, no assistant, voice never attached (old attach-after-Cursor path). Client then spun processing on orphan last-user (see iOS `task-bug-chat-eternal-processing-orphan-user.md`).
