# Structured UI

**Code:** `kb_app_api/structured_ui/`, `routes/ui_events.py`, `routes/remote_ui.py`, agent prompt `agent/structured_ui_agent_prompt.md`

## What it is

JSON **screen documents** (`schema_version: 1`) the iOS client renders as interactive UI (forms, lists, callouts, …). Used in chat (agent replies / ui-events) and in boards (`rendered_document` / remote providers).

## Chat ui-events

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/sessions/{session_id}/ui-events` | Body: action / component / values → `{ screen, messages }` |

Flow (`structured_ui/agent.py`):

1. Validate / parse agent JSON (`validate_screen_document`, `parse_agent_ui_event_payload`).
2. Prefer live agent resolution; fall back to mock flow when disabled or on parse errors.
3. Client capability: headers may gate SUI (`client_metadata.structured_ui_allowed_from_headers`).

## Remote UI proxy

| Method | Path | Notes |
|--------|------|--------|
| GET | `/api/remote-ui?url=…` | Proxy GET to absolute URL |
| GET | `/api/remote-ui/allowlist` | Allowed hosts |

Env: `REMOTE_UI_HOST_ALLOWLIST` (hostnames only, e.g. `127.0.0.1,localhost,lyrics.example.com`). Schemes limited; no open proxy to arbitrary internet hosts.

Boards provider `remote_structured_ui` uses the same allowlist idea for Overview/Actions remote screens.

## Schema

- Document: `{ "schema_version": 1, "screen": { "type", "id", "children": […] } }`
- Validation errors → API error / mock fallback depending on path
- Do not duplicate the full component tree here — see validator + iOS renderer + contract

## Tests

- `kb_app_api/tests/test_structured_ui.py`
