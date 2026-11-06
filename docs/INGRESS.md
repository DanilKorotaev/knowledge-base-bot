# Event Ingress API

Per-user webhook entry for automation (CI, mail pollers, Grafana, cron, …).  
No GitHub-specific routes in the API core. No personal vault paths in code — configuration is per-user via authenticated endpoints (agent-driven).

## Public ingest

```http
POST /api/ingress/{token}
Content-Type: application/json

{
  "source": "ci",
  "type": "ci.workflow_failed",
  "summary": "Short title for the chat bubble",
  "detail": "Optional long body (collapsed in UI)",
  "hints": { "commit_message": "…" },
  "payload": { },
  "links": [{ "title": "Run", "url": "https://…" }],
  "dedupe_key": "unique-per-user"
}
```

Also accepts `multipart/form-data` with a `payload` JSON field plus files (file bytes are size-audited; persistence policy is expandable).

Token path is enough for the caller. Create/revoke tokens as the signed-in user.

## Management (Bearer — same auth as other `/api/me/*` routes)

| Method | Path | Purpose |
|--------|------|---------|
| GET/POST | `/api/me/ingress/tokens` | list / create (raw token once) |
| POST | `/api/me/ingress/tokens/{id}/revoke` | revoke |
| GET/PUT/DELETE | `/api/me/ingress/adapters` | dynamic participant registry |
| POST | `/api/me/ingress/avatars` | upload participant avatar (`multipart`, `participant_key` + `file`) |
| GET | `/api/ingress/avatars/{id}` | fetch avatar bytes (public; id is unguessable) |
| GET/PUT | `/api/me/ingress/bindings` | `session_key` → `session_id` |
| GET/POST/DELETE | `/api/me/ingress/rules` | match / extract / action |
| PUT | `/api/me/ingress/scripts` | registered script actions |
| GET | `/api/me/ingress/events` | recent events (slim) |

Avatar files are stored next to the API database (`ingress_avatars/`), not in the vault.

### Token labels

When creating a token, set human-readable fields:

- `label` — short name, e.g. `CI: knowledge-base-app-ios`
- `description` — where it is used, e.g. `GitHub Actions secret KBAPP_INGRESS_URL in DanilKorotaev/knowledge-base-app-ios`

On create, response may include `ingress_url` if `KB_APP_PUBLIC_BASE_URL` is configured (full URL for the secret).

## CI adapter (GitHub Actions)

Script: `scripts/ci/kbapp_ingress_notify.py`

```bash
# Repository secret (full URL, one per repo):
# KBAPP_INGRESS_URL=https://<public-host>/api/ingress/<token>

python3 scripts/ci/kbapp_ingress_notify.py tests --outcome failure
python3 scripts/ci/kbapp_ingress_notify.py deploy --outcome success
```

Envelope uses `source=github_actions`, `adapter_key=github_actions`.  
Session routing via user rules (extract `KB-Session:` from commit message) — prompts/rules live in the vault, not in this repository.

### Token sandbox fields

- `allow_enqueue_agent` / `allow_script`
- `agent_runtime`: `none` | `container` | `host`
- `agent_prompt_profile`: default `untrusted_ingress` (injection-aware addendum when enqueueing)

### Rule action kinds

- `session` — deliver `role=external` message (+ optional agent job)
- `script` — invoke a registered script descriptor
- `orchestrator` — resolve binding key `orchestrator` (AI router session)

Extract patterns (e.g. `KB-Session:` from commit messages) live in **rule JSON**, not in repository code.
