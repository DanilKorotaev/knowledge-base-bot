# Voice & query jobs

**Code:** `routes/voice.py` (`/api/query/…`), `routes/jobs.py` (`/api/jobs`), `kb_app_api/query_jobs/`

## Voice / query entrypoints

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/query/voice/transcribe` | Multipart `audio` → text |
| POST | `/api/query/voice` | Multipart: required `session_id`, `audio` **or** `transcription_hint` |
| POST | `/api/sessions/{id}/messages/voice` | Session-scoped voice message (see [sessions-messages.md](sessions-messages.md)) |

Transcription uses OpenAI / configured transcription service. Structured UI may be gated by client headers (`structured_ui_allowed_from_headers`).

## Query jobs

Long Cursor runs are **background jobs** so uvicorn workers are not blocked for the whole agent turn.

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/jobs/active` | Jobs for current user (Overview board / polling) |
| DELETE | `/api/jobs/{job_id}` | Cancel |

Public job shape: id, status, truncated query text, session id, timestamps (see `routes/jobs.py`).

SSE bridge: `query_jobs/sse_bridge.py` — streams assistant deltas into the messages SSE response when the client keeps the connection open.

The **Активные запросы** board preset (`system_query_jobs` provider) lists/cancels the same jobs — [boards-presets.md](boards-presets.md).

## Tests

- Voice / compose paths in `kb_app_api/tests/`
- Board provider: `test_board_providers_extra.py` (`system_query_jobs`)
