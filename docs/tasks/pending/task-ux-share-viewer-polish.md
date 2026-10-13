# UX: Public share viewer polish

**Status:** Backlog  
**Priority:** Low  
**Related:** `task-feature-shared-chat-public-link` (done)

## Context

MVP share HTML renders assistant markdown (headings, bold, lists, code, basic tables/links). QA OK for reading chats.

## Later improvements

- [ ] Tables: better layout on mobile (horizontal scroll, zebra, sticky header)
- [ ] Links: ensure all markdown/autolink URLs are clearly tappable; optional in-app preview
- [ ] Attachments: share-scoped download URLs (images/voice) — phase 2 of share epic
- [ ] Structured UI read-only render in share page
- [ ] “Copy link” / “Create new link without revoking previous” (today POST rotates = old URL 404)
- [ ] Dark mode / typography parity with iOS chat bubbles

## Note on “invalid / expired” after refresh

`POST /api/sessions/{id}/share` **rotates** the token (revokes previous). Creating a new share in app or via API invalidates the old URL — expected for MVP.
