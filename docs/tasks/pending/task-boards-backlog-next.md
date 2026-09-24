# Boards / Overview — backlog после MVP

Срез «список + vault KPI + MCP upsert» уже есть. Ниже — что ещё хотели и не сделали.

## Уже есть

- Overview на iOS, Structured UI (`metric` / `table`)
- `GET/PUT/DELETE/refresh` boards, definitions в БД
- Provider `vault_frontmatter_agg` (dotted fields + sidecar блока)
- MCP `kb-boards` + skill (токен из `~/Projects/.../.env`, не из synced `mcp.json`)
- Пустой open-source seed; личные борды только в БД / через агента

## Не сделано (по приоритету смысла)

1. **Авто-refresh после записи агентом** — hook «заметка type:X сохранилась → invalidate board Y» (сейчас только pull-to-refresh / `boards_refresh`).
2. **Период / фильтр на экране** (месяц, 3 мес) — отложено; сейчас полный пересчёт при refresh.
3. **In-app agent tools** — MCP для Cursor на mini есть; tools внутри чата приложения (без отдельного MCP process) — позже.
4. **Settings toggle Overview** как Health + подключение skill к сессии.
5. **System board: active query jobs** + cancel.
6. **Remote boards** (VPN/monitor → structured_ui).
7. **Charts**, device/watch блоки, vault_script provider.
8. **Кэш worker** (deps watcher / interval), чтобы не сканировать vault на каждый GET при росте данных.
9. **Multi-user auth** для MCP: bearer пользователя, не общий static token.

## Как обновляется блок тренировок

Sidecar читает `Тренировки/Блоки` с `status: active`. Новый абонемент = новая заметка `active`, старая `completed` — definition борда не трогаем, достаточно refresh.
