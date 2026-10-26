# Feature: Telegram bot scoped to App `user_id`

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** Telegram bot  
**Эпик:** [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)  
**Depends on:** [task-api-telegram-account-link-1to1.md](task-api-telegram-account-link-1to1.md), [task-feature-telegram-invite-no-password.md](task-feature-telegram-invite-no-password.md)

## Цель

Бот перестаёт жить в мире «whitelist telegram_id = user». Каждый апдейт:

1. `telegram_id` → lookup App user.
2. Если нет связи → отказ / инвайт / «привяжи в Settings».
3. Сессии, сообщения, vault, Cursor isolation — **как у KB App API** для этого `user_id`.

## Чеклист

- [ ] Middleware: resolve user или short-circuit
- [ ] Убрать/сузить `ensure_user(telegram_id)` auto-create для продакшена
- [ ] Sessions list / active session / query pipeline берут `user_id`
- [ ] Sync / NC: `SyncService.for_user` (App Password), не bot share для personal vault
- [ ] Soft-jail / `cursor_isolation` с профиля user
- [ ] Админ-команды бота: либо только linked admins (`role=admin`), либо deprecate в пользу admin web
- [ ] Регрессионные тесты на isolation между двумя linked users

## Не в этой задаче

- Markdown / channel prompt → [task-feature-telegram-markdown-and-channel.md](task-feature-telegram-markdown-and-channel.md)
- Mini App UI → web-эпик
