# KB App API: фоновые jobs для Cursor-запросов (без привязки к числу uvicorn workers)

**Статус:** ✅ P0 реализовано (2026-09-12) — `query_jobs` + worker + SSE bridge через `query_job_events`  
**Приоритет:** 🔴 Высокий (стабильность API при параллельных чатах)  
**Категория:** KB App API / архитектура  
**Связи:** iOS push/poll уже есть; interim `KB_APP_API_WORKERS` больше не нужен как основной фикс

## Что сделано (P0)

- Таблицы `query_jobs` + `query_job_events` (Postgres + SQLite `init_db`).
- `QueryJobService` (enqueue / claim / events / complete / fail / reclaim stale).
- Отдельный процесс: `python -m kb_app_api.query_jobs.worker`  
  (`scripts/start-kb-app-query-worker.sh` + LaunchAgent `com.coredan.kb-app-query-worker`).
- API при `KB_APP_QUERY_JOBS_ENABLED=true` (default в `start-kb-app-api-host.sh`):
  - ставит job, **не** держит Cursor в uvicorn;
  - SSE читает `query_job_events` и отдаёт те же `delta` / `activity` / `done` — **стриминг сохранён**.
- Deploy: bootstrap query worker **без** `kickstart -k` (не убивает Cursor); API safe-restart как раньше.

## Критерии приёмки

- [x] Unit: enqueue/claim/events + SSE bridge (`test_query_jobs.py`).
- [ ] После CI: worker в launchd; compose SSE в приложении стримится.
- [ ] Рестарт API mid-query не рвёт Cursor (worker живёт отдельно).
- [ ] `GET /health` / `GET /sessions` отзывчивы при длинном Cursor.

## P1 (не в этом PR)

- [ ] `DELETE /api/jobs/{id}` cancel.
- [ ] `GET …/jobs/active`.
- [ ] NOTIFY/LISTEN вместо poll.
- [ ] Attachments route через jobs (сейчас text/voice/compose).
- [ ] Fair queue per user.

## Включение

- Host API: `KB_APP_QUERY_JOBS_ENABLED=true` (уже default в start script).
- Worker: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.coredan.kb-app-query-worker.plist`
- Откат: `KB_APP_QUERY_JOBS_ENABLED=false` → старый in-process Cursor.
