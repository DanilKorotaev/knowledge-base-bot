# Feature: Organic Structured UI in normal chat replies

**Status:** done (2026-08-28)  
**Vault:** `Документация/Задачи/task-structured-ui-next.md` §2B

## Shipped

- [x] Full schema v1 in `_PROMPT` + anti-meta
- [x] Attach when reply asks for a choice (even if options are in text)
- [x] `reply_likely_needs_ui()` heuristic — skip LLM for plain statements
- [x] Unit tests

## References

- `kb_app_api/structured_ui/reply_suggest.py`
- `kb_app_api/tests/test_structured_ui_reply_suggest.py`
