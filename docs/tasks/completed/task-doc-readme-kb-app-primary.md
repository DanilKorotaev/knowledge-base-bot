# Doc: README — KB App backend primary, Telegram deprecated

**Статус:** ✅ Done (2026-10-26)  
**Приоритет:** 🔴 Высокий  
**Категория:** Documentation  
**Эпик доков:** [../pending/task-epic-documentation-refresh.md](../pending/task-epic-documentation-refresh.md)

## Что хотели добиться

Корневой `README.md` и `docs/README.md` описывают **реальный продукт**:

- Бэкенд Knowledge Base App (JWT, per-user vault, boards, push…), не «Telegram-бот».
- Telegram bot + Mini App: **deprecated**, одна ссылка на [task-epic-telegram-multiuser.md](../pending/task-epic-telegram-multiuser.md).
- Быстрый старт: API / compose, не `python bot.py` как главный путь.

## Чеклист

- [x] Переписать корневой README
- [x] Обновить `docs/README.md` (секция Deprecated + ссылка на эпик)
- [x] Убрать whitelist-бота как основной access control из лица репо
- [x] CI Telegram notifications отдельно от user bot

## Не в этой задаче (осталось в эпике)

- Полный перенос файлов в `docs/telegram/`
- Детальные feature guides API
- Pause бота на host (осознанно отложено)
