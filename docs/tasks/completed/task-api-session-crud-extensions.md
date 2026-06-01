# KB App API: удаление и редактирование сессий

**Статус:** ✅ Выполнено  
**Дата завершения:** 2026-06-01  
**iOS:** [task-feature-session-delete-rename.md](../../../knowledge-base-app-ios/docs/tasks/completed/task-feature-session-delete-rename.md)

## Реализовано

- `DELETE /api/sessions/{session_id}` → soft delete (`status=deleted`), `{ "success": true }`
- `PATCH /api/sessions/{session_id}` → `{ "title": "…" }`, ответ `{ "session": … }`
- Smoke: `test_delete_and_patch_session`
