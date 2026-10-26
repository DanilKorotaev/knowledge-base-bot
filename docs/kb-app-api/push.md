# Push (APNs)

**Code:** `routes/devices.py`, `apns_push_service.py`, `push_dispatch.py` (and DB `user_devices`)

## Device registration

Prefix: `/api/devices` (Bearer).

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/devices` | Body: `device_token`, `platform` (`ios`), `apns_environment` (`sandbox`\|`production`), optional `app_version` → **204** |
| DELETE | `/api/devices/{device_token}` | Unregister → **204** |

Tokens are **per user** (`upsert_user_device` / `delete_user_device`). Multi-account iOS clients should register after login and unregister on full logout for that account.

## Delivery

- Server sends via APNs using host env / secrets (key id, team, bundle, `.p8` — **not** in git).
- `apns_environment` on the device row selects sandbox vs production gateway.
- Dispatch hooks into query-job completion / notifications (`push_dispatch`) so background Cursor work can wake the app.

## Ops

Configure APNs only on Mac mini / staging secrets. Public docs must not embed real bundle hostnames beyond placeholders.

## Related

- iOS contract: devices section (if present) / client push registration code
- [voice-jobs.md](voice-jobs.md) — jobs that may trigger push
