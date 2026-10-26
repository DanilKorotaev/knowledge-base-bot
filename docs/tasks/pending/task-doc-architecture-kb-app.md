# Doc: ARCHITECTURE — KB App multi-user

**Статус:** 📋 Planned  
**Приоритет:** 🔴 Высокий  
**Категория:** Documentation  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)

## Что хотим добиться

`docs/ARCHITECTURE.md` отражает текущую систему:

```
iOS App ──JWT──► kb_app_api ──► Postgres
                      │
                      ├── Cursor CLI (per-user isolation / vault)
                      ├── Nextcloud (per-user App Password + kb_folder)
                      ├── Boards / Structured UI / Push / Query jobs
                      └── (optional later) Telegram bot / Mini App / Web
```

- Host prod LaunchAgent vs staging Docker
- Soft-jail `strict` vs `host`
- Что deprecated: bot-primary, shared Bearer, single `LOCAL_KB_PATH` для всех

Bot/Mini App детали — ссылка на `docs/telegram/`, не дублировать длинно.

## Чеклист

- [ ] Новая диаграмма(ы)
- [ ] Список компонентов `kb_app_api/*` на уровне модулей (не каждый файл)
- [ ] Связь с iOS contract и vault layout `users/<login>/`
- [ ] Секция «Legacy Telegram» → epic + folder
