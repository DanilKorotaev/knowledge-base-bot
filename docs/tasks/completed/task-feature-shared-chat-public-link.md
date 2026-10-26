# Feature: Share chat as read-only public URL

**Status:** Done (merged to develop + iOS main; host default PUBLIC_BASE_URL)  
**Priority:** Medium–High  
**iOS:** overflow menu Share → system sheet  
**Vault:** foundation for future web KB App

## Goal

Owner creates an opaque share token for a session. Anyone with the URL can **read** the dialogue; no edit/send. Later: fork into own account (ChatGPT-style).

## Constraints

- Do **not** expose `KB_APP_API_TOKEN` (single shared bearer today).
- Public routes are token-scoped only; ownership APIs stay Bearer-authenticated.

## MVP

- [x] Table `session_shares` (token hash, session_id, expires_at, revoked_at) — SQLite + Postgres `init_db`
- [x] `POST/DELETE /api/sessions/{id}/share` (owner Bearer)
- [x] `GET /api/share/{token}` JSON (no write; strip attachment `download_url`)
- [x] Minimal HTML viewer `GET /share/{token}`
- [x] Config: `KB_APP_PUBLIC_BASE_URL`, `KB_APP_SHARE_DEFAULT_TTL_DAYS`
- [x] Tests: `kb_app_api/tests/test_session_share.py`
- [x] iOS: Share in overflow menu → `UIActivityViewController`

## Ops

`scripts/start-kb-app-api-host.sh` expects `KB_APP_PUBLIC_BASE_URL` from the environment (no real prod FQDN in git).
Override in `.env` if the public hostname changes. Optional: `KB_APP_SHARE_DEFAULT_TTL_DAYS=30`.

## Phase 2

- Attachments via share-scoped URLs
- Structured UI read-only render
- Rate limits / audit
- Fork session into caller’s account (needs multi-user auth epic)
