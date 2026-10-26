# Sessions, messages, compose, share

**Code:** `routes/sessions.py`, `messages.py`, `attachments.py`, `share.py`, `files.py`, `ui_events.py`  
**Contract:** iOS `KB_APP_API_CONTRACT.md` (sessions / messages sections)

## Sessions

Prefix: `/api/sessions` (Bearer).

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/sessions` | Paginated list |
| GET | `/api/sessions/archived` | Archived |
| GET | `/api/sessions/search` | `q` — id or text |
| POST | `/api/sessions` | Create (`title`, `use_knowledge_base`) |
| PATCH | `/api/sessions/{id}` | Title |
| POST | `…/archive`, `…/restore` | Soft archive |
| DELETE | `/api/sessions/{id}` | Soft delete |
| POST | `…/share` | Mint public share token + URLs |
| DELETE | `…/share` | Revoke |

Share URLs use host `KB_APP_PUBLIC_BASE_URL` (host `.env` / LaunchAgent — **never** commit real FQDNs). Public viewers: `GET /api/share/{token}` (JSON), `GET /share/{token}` (HTML).

## Messages

Under `/api/sessions/{session_id}/…`:

| Method | Path | Notes |
|--------|------|--------|
| GET | `/messages` | `limit`, `before` — older page |
| POST | `/messages` | Text query → JSON or **SSE** stream |
| POST | `/messages/compose` | Multipart text + files + optional audio |
| POST | `/messages/voice` | Multipart transcription + audio |
| POST | `/attachments` | File attach (+ optional follow-up query) |
| GET | `/attachments/{id}/file` | Binary download |
| POST | `/ui-events` | Structured UI action (see [structured-ui.md](structured-ui.md)) |

Heavy Cursor work runs as a **query job** (see [voice-jobs.md](voice-jobs.md)); HTTP may stream SSE deltas/activity while the job runs.

Uploads land under the **user vault** session upload root (`resolve_kb_root` / session paths).

## Files (working copy)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/files/changes` | Optional `session_id` |
| POST | `/api/files/revert` | `{ file_id }` |
| POST | `/api/files/open-link` | Authenticated NC open link |
| POST | `/api/files/share-link` | Public NC share link |

Paths are vault-/NC-relative via `to_vault_relative`.

## Flow (happy path)

1. Client Bearer → create or reuse session.
2. `POST …/messages` or compose/voice → persist user message, start query job.
3. SSE and/or push deliver assistant text / structured UI.
4. File changes recorded; sync to NC with per-user App Password.

## Tests

- `kb_app_api/tests/test_smoke.py`, session list performance, share/message suites as present under `kb_app_api/tests/`
