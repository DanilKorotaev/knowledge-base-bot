# KB App API — Prometheus `/metrics`

**Статус:** 📋 Запланировано  
**Приоритет:** 🟡 Средний  
**Категория:** Observability / kb_app_api  
**Связано:** мониторинг на Mac mini (Grafana Apps overview, blackbox `/health` уже есть)

## Контекст

На Mac mini крутятся Loki/Prometheus/Grafana. Nextcloud и nginx уже в scrape; для KB App API сейчас только **blackbox** на `GET /health` (prod `:8091`, staging `:8191`) — up/down и latency, без RPS, ошибок и разбивки по роутам.

Нужен нативный endpoint метрик в FastAPI, чтобы Prometheus на mini забирал ряды и алерты/дашборд стали полезными для нагрузки бота и iOS-приложения.

Канон инфраструктуры (vault): `Документация/Инфраструктура/Мониторинг — Loki Grafana на Mac mini.md`.

## Цель

1. Отдавать Prometheus text format на **`GET /metrics`** (без auth, как `/health`; не светить секреты).
2. Стандартные HTTP-метрики: requests total, latency histogram, in-progress, по `method` + `path`/`handler` (низкая cardinality — шаблоны путей, не raw id).
3. Пара кастомных gauges/counters по желанию: active background jobs, размер очереди query jobs (если дёшево).
4. Подключить scrape в `~/srv/monitoring/prometheus.yml` на mini (`host.docker.internal:8091/metrics`) и панели в Apps overview / отдельный ряд KB.
5. Алерт Grafana (опционально): `probe_success == 0` уже можно; плюс `rate(http_requests_5xx) > N`.

## Предлагаемый стек

- `prometheus-fastapi-instrumentator` **или** `prometheus_client` + middleware вручную.
- Не ломать существующий `/health`.
- Staging (`:8191`) получает то же после деплоя.

## Задачи

- [ ] Выбрать библиотеку, добавить в `requirements.txt` / lock.
- [ ] Подключить instrumentator (или middleware) в `kb_app_api/main.py`.
- [ ] Исключить/сгруппировать high-cardinality path params (`session_id`, `board_id`, …).
- [ ] Smoke-тест: `GET /metrics` содержит `http_requests` / process metrics; тест в `kb_app_api/tests/`.
- [ ] Документ: `kb-app-api/README.md` или env.example — одна строка про `/metrics`.
- [ ] После merge: scrape + панели на mini (отдельный маленький шаг в vault monitoring, можно тем же PR не трогать).

## Вне скоупа

- Метрики Telegram long-polling бота (`bot.py`) — отдельная задача.
- `postgres_exporter` для `knowledge-base-bot-db` — отдельная задача (инфра).
- nginx 5xx по vhost — не этот репозиторий.

## Приёмка

```bash
curl -sS http://127.0.0.1:8091/metrics | head
# с mini после scrape:
# Prometheus target kb-app-api UP; в Grafana видны RPS/latency
```

## Связанные файлы

- `kb_app_api/main.py`
- `kb_app_api/routes/health.py`
- `kb_app_api/tests/test_smoke.py`
- `requirements.txt`
