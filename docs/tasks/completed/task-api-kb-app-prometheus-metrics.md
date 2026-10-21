# KB App API — Prometheus `/metrics`

**Статус:** ✅ Сделано (2026-10-21)  
**Приоритет:** 🟡 Средний  
**Категория:** Observability / kb_app_api  

## Результат

- `prometheus-fastapi-instrumentator` + `GET /metrics` (без auth)
- Templated handlers, `/health` и `/metrics` исключены из HTTP-метрик
- Smoke: `test_metrics_prometheus`
- Доки: `kb-app-api/README.md`, `env.example`

После деплоя на mini: scrape `host.docker.internal:8091/metrics` в Prometheus (vault monitoring).

Исходный бэклог: был в `docs/tasks/pending/`.
