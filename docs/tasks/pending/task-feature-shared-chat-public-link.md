# Feature: Share chat as read-only public URL

**Status:** Backlog  
**Priority:** Medium–High  
**iOS:** overflow menu Share → system sheet  
**Vault:** foundation for future web KB App

## Goal

Owner creates an opaque share token for a session. Anyone with the URL can **read** the dialogue; no edit/send. Later: fork into own account (ChatGPT-style).

## Constraints

- Do **not** expose `KB_APP_API_TOKEN` (single shared bearer today).
- Public routes are token-scoped only; ownership APIs stay Bearer-authenticated.

## MVP (~2–4 days)

- Table `session_shares` (token hash, session_id, expires_at, revoked_at)
- `POST/DELETE /api/sessions/{id}/share` (owner)
- `GET /api/share/{token}` + messages page (no write)
- Minimal static/web read-only viewer
- iOS: Share action copies/opens URL

## Phase 2

- Attachments via share-scoped URLs
- Structured UI read-only render
- Rate limits / audit
- Fork session into caller’s account (needs multi-user auth epic)
