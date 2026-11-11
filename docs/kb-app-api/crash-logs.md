# iOS crash logs

The phone uploads the log file of the crashed session. The crash report itself arrives later or earlier through ingress. They meet on `log_session`.

## App

`POST /api/crash-logs` with the user Bearer token and `multipart/form-data`:

- `log_session`
- `app_version`
- `app_build`
- `file` — plain text, last 4 MB kept

`403` with `error.code = crash_logs_disabled` means the admin switch is off. The client should stop retrying until the user turns upload back on.

## Admin

Same JWT as `/api/admin/users` (`require_admin`).

| Method | Path | Body |
| --- | --- | --- |
| GET | `/api/admin/settings` | `{ "accept_crash_logs": true }` |
| PATCH | `/api/admin/settings` | `{ "accept_crash_logs": false }` |
| GET | `/api/admin/crash-logs/{log_session}` | the file |

The switch is also on `/admin/`. Default is on. Files live under `KB_CRASH_LOG_DIR` or `~/Library/Application Support/kb-app-api/crash-logs`, not in the vault and not in git.

## Ingress

A reader of Crashlytics posts the usual envelope. The API sets `hints.logs_status` to `ready` or `pending` before the event is stored. `hints.code_state` is the git tag of the build. That tag is the tree where the process crashed. It is not the commit that introduced the defect.

When the file arrives after the report has already been delivered, the API writes a second external message `type=app.crash_logs` into the same chat session.

User rule (not hardcoded):

```json
{
  "priority": 10,
  "match": { "source": "ios", "type": ["app.crash", "app.crash_logs"] },
  "action": {
    "kind": "session",
    "session_key": "ios-crashes",
    "policy": "enqueue_agent"
  }
}
```

Create a chat session, a binding `ios-crashes` to that session, and an ingress token whose `allowed_sources` is `["ios"]` with `allow_enqueue_agent` on. Without the binding, the existing orchestrator receives the event.
