# API: Cursor isolation per-user (`strict` | `host`)

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Высокий после auth  
**Категория:** Security / Cursor  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** `task-api-auth-nextcloud-users`

## Цель

У каждого пользователя свой режим изоляции Cursor **в одном окружении**:

- **`strict`**: процесс видит только `vault_root` (Docker/bubblewrap bind + deny path escape)
- **`host`**: текущее поведение Mac mini (cwd = vault, FS шире) — для выбранных аккаунтов

Дефолт инстанса — только при создании юзера; дальше поле на `users.cursor_isolation`.

## Чеклист

- [ ] Поле + admin/API set
- [ ] Query worker / CursorCLIService читает isolation юзера сессии
- [ ] Реализация `strict` (предпочесть тот же Docker, что staging, или sandbox на host)
- [ ] Тесты: strict не читает соседний `users/other/`
- [ ] Staging дефолт для новых = `strict`; личный admin может быть `host`
