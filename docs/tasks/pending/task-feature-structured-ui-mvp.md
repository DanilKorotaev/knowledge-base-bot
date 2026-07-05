# Feature: Structured UI MVP (backend-driven JSON screen)

**Status:** In progress (feature branch `feature/structured-ui-mvp`)  
**Priority:** High  
**Related (iOS):** `knowledge-base-app-ios/docs/tasks/pending/task-feature-structured-ui-mvp.md`  
**Spec:** Obsidian «Задачи — MVP JSON-экран (backend-driven UI)»

## Goal

E2E mock flow: server returns `structured_ui` JSON → iOS renders vstack/text/button → tap sends `POST …/ui-events` → next screen + chat history stubs.

## Scope (MVP-5…7, MVP-9 partial)

- [x] Schema v1 validator (`vstack`, `text`, `button`; depth/node/size limits)
- [x] In-memory store keyed by assistant `message_id` (no DB migration yet)
- [x] `POST /api/sessions/{session_id}/ui-events` with mock FSM (`start` → yes/no → done)
- [x] `structured_ui` on messages via enrichment + serializers
- [x] Unit + HTTP tests (`kb_app_api/tests/test_structured_ui.py`)
- [x] JSON Schema + fixture (`kb_app_api/structured_ui/schema_v1.json`)
- [x] Persist `structured_ui` on `messages` row (SQLite + PostgreSQL migration)
- [x] LLM agent path for `ui-events` (`STRUCTURED_UI_AGENT_ENABLED`, mock fallback)
- [ ] OpenAPI in bot repo (canonical copy lives in iOS `docs/openapi/`)
- [ ] LLM on regular text messages (post-MVP)

## Deploy

Roll out on `feature/structured-ui-mvp` separately from iOS. Rollback = revert branch / disable route.

**Agent mode:** set `STRUCTURED_UI_AGENT_ENABLED=true` on the API server (requires `CURSOR_API_KEY`).  
Keep `STRUCTURED_UI_AGENT_MOCK_FALLBACK=true` (default) so unknown/bad LLM output falls back to the mock FSM.

## Acceptance

- [ ] `python -m unittest kb_app_api.tests.test_structured_ui -v` green
- [ ] Manual: create session → `POST ui-events` `{action_id:start}` → GET messages shows `structured_ui`
- [ ] Button tap returns new screen + `[UI] …` user stub in history
