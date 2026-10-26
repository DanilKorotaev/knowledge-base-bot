# Health & metrics

**Code:** `routes/health.py`, `kb_app_api/metrics.py`

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| GET | `/health` | public | Liveness `{ "status": "ok" }` — used by LaunchAgent / Docker healthchecks |
| Metrics | Prometheus scrape (see `setup_metrics`) | env-dependent | Process/request metrics for host monitoring |

Prod host checks: `scripts/safe-restart-kb-app-api-host.sh` waits on `http://127.0.0.1:8091/health`.

Ops map: [../OPS.md](../OPS.md).
