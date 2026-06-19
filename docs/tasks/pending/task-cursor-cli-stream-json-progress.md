# Cursor CLI: stream-json, прогресс tool calls и activity-based таймауты

**Статус:** 🚧 В работе (фазы 1–2 на бэкенде)  
**Приоритет:** 🟡 Средний (UX + ложные таймауты на тяжёлых задачах)  
**Категория:** KB App API / Cursor CLI / Telegram bot  
**Связи:** iOS [task-ux-cursor-activity-streaming.md](../../../knowledge-base-app-ios/docs/tasks/pending/task-ux-cursor-activity-streaming.md), [task-ux-long-query-feedback.md](../completed/task-ux-long-query-feedback.md), [task-feature-streaming-responses.md](../completed/task-feature-streaming-responses.md), [Cursor CLI output format](https://cursor.com/docs/cli/reference/output-format)

## Проблема

Сейчас `cursor-agent` запускается как:

```text
cursor-agent -p --force [--resume <chatId>] "<запрос>"
```

Формат вывода по умолчанию — **`text`**: в stdout попадает только финальный текст ответа. Пока агент читает файлы, гоняет shell (`swift test`, `xcodebuild`, OAuth и т.д.), stdout **молчит**.

Бэкенд (`cursor_cli_service.process_query`) считает запрос «зависшим», если за `CURSOR_CLI_TIMEOUT` (600 с) **не пришёл первый непустой текстовый чанк** → пользователь видит ошибку, хотя PID жив и работа идёт (пример: сессия 159, 2026-06-18).

## Цель

1. Видеть **активность агента до финального ответа** (tool calls, init).
2. Не обрывать долгие запросы из‑за «тишины stdout» при работающих инструментах.
3. Сохранить обратную совместимость (`text` режим для `run_simple_prompt` / полировки голоса).
4. Подготовить SSE-события `activity` для iOS (фаза 2, отдельная задача).

## Решение (обзор)

Включить **`--output-format stream-json`** для `process_query` (не для `run_simple_prompt`).

Парсить NDJSON построчно. События:

| Тип | Смысл для нас |
|-----|----------------|
| `system` / `init` | Агент стартовал |
| `tool_call` / `started` | Прогресс («читает файл», «запускает shell») |
| `tool_call` / `completed` | Опционально в лог / UI |
| `assistant` | Текст ответа (сегменты между tool calls) |
| `result` / `success` | **Канонический** полный ответ для БД |

Таймаут «до первого вывода» заменить на **«до первого любого NDJSON-события»** (activity-based).

---

## Фаза 1 — Backend: stream-json без partial output

**Флаги:**

```text
cursor-agent -p --force --output-format stream-json ...
```

`--stream-partial-output` **не** включать (проще парсинг, меньше дублей текста).

### Задачи

- [x] **Конфиг** (`config.py`, `docs/DEVELOPMENT.md`):
  - `CURSOR_CLI_OUTPUT_FORMAT` = `text` | `stream-json` (дефолт `stream-json`).
  - `CURSOR_CLI_STREAM_PARTIAL_OUTPUT` (дефолт `false`).
- [x] **Модуль парсера** `services/cursor_stream_parser.py`
- [x] **Интеграция в `cursor_cli_service.process_query`**
- [x] **`run_simple_prompt`** — без изменений (`text` режим).
- [x] **Тесты** (`services/tests/test_cursor_stream_parser.py`)
- [ ] **`.env.example`** — добавить новые переменные (при доступе к файлу)

### Критерии приёмки фазы 1

- [ ] Запрос «начни реализацию + тесты» не падает по таймауту, пока идут `tool_call` без текста (при живом cursor-agent).
- [ ] В логах видны tool_call и время до первого события.
- [ ] Ответ в БД совпадает с `result.result`.
- [ ] Полировка транскрипции (`run_simple_prompt`) не затронута.
- [ ] Режим `CURSOR_CLI_OUTPUT_FORMAT=text` работает как раньше (rollback).

---

## Фаза 2 — SSE `activity` для KB App API

### Задачи

- [x] **`kb_app_api/routes/messages.py`**: SSE `{"activity":"tool","label":"…"}`
- [x] **Контракт:** `KB_APP_API_CONTRACT.md` — поле `activity` / `label`
- [x] **Тест:** `test_sse_disconnect` обновлён под новый формат очереди
- [ ] **Тест:** mock `on_activity`, assert event в потоке (отдельный unit)

### Критерии приёмки фазы 2

- [ ] При SSE-запросе клиент получает `processing` → один или несколько `activity` → `delta` → `done`.
- [ ] Старый iOS-клиент без поддержки `activity` не ломается.

---

## Фаза 3 — `--stream-partial-output` (плавный стрим текста)

**Флаги:**

```text
--output-format stream-json --stream-partial-output
```

Env: `CURSOR_CLI_STREAM_PARTIAL_OUTPUT=true`.

### Задачи

- [ ] Расширить парсер `assistant` по правилам Cursor:
  - **Брать:** `timestamp_ms` есть, `model_call_id` нет → streaming delta.
  - **Пропускать:** `model_call_id` есть (дубль перед tool call) и финальный flush без `timestamp_ms`.
- [ ] Юнит-тесты на три формы `assistant` (см. [forum](https://forum.cursor.com/t/stream-partial-output-assistant-events-have-multiple-undocumented-forms-how-should-consumers-parse-them/156289)).
- [ ] Документация: когда включать partial (UX) vs только tool progress (фаза 1).

### Критерии приёмки фазы 3

- [ ] В чате iOS typewriter идёт чаще и ровнее, без дублирования абзацев.
- [ ] Финальный текст в БД по-прежнему из `result.result`.

---

## Фаза 4 — Telegram bot UX (опционально)

- [ ] В `query_processing_service` при stream-json обновлять статусное сообщение («⏳ …») текстом последней `activity` (с throttle, как `QUERY_PROGRESS_TIMER_INTERVAL`).
- [ ] Не спамить edit_message чаще N с.

---

## Деплой

- [ ] `CURSOR_CLI_OUTPUT_FORMAT=stream-json` в `.env` на Mac mini после прохождения тестов.
- [ ] Запись в `docs/DEPLOYMENT_SERVER.md`.
- [ ] Smoke: один лёгкий и один тяжёлый запрос на staging/mini.

## Риски

| Риск | Митигация |
|------|-----------|
| NDJSON + PTY ломает строки | В stream-json режиме — pipe, не PTY |
| Смена схемы событий Cursor | Парсер tolerant, unknown → log debug |
| `result` не пришёл (crash) | Fallback текст + stderr в лог; понятная ошибка пользователю |
| Долгий shell без новых событий | Увеличить `CURSOR_CLI_TIMEOUT` или heartbeat по `tool_call` completed → started |

## Не в scope

- Фоновые query jobs ([task-api-background-query-jobs.md](task-api-background-query-jobs.md)) — отдельно.
- Отображение activity в iOS UI — [task-ux-cursor-activity-streaming.md](../../../knowledge-base-app-ios/docs/tasks/pending/task-ux-cursor-activity-streaming.md).

## Зависимости

- `cursor-agent` на mini с поддержкой `--output-format stream-json` (текущая версия 2026.06.x — ок).
- iOS фаза 2+ зависит от SSE `activity` в API.
