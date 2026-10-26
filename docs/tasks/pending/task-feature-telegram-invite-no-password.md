# Feature: invite without password via Telegram

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** Auth / Telegram  
**Эпик:** [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)  
**Depends on:** [task-api-telegram-account-link-1to1.md](task-api-telegram-account-link-1to1.md)

## Цель

Админ (или invite-only mode) создаёт пользователя **без пароля** и шлёт приглашение в Telegram. Принятие инвайта:

1. Создаёт/активирует App-user (`must_change_password` / set-password).
2. Сразу пишет `telegram_id` → связь 1:1.
3. Дальше бот/мини-ап работают только от этого `user_id`.

**Не допускается** создание сессий от «голого» `telegram_id` до link.

## Потоки

### A. Telegram-first invite (v1)

1. Admin API: `POST /api/admin/users` с `invite_via: telegram`, `telegram_id` или username.
2. Бот шлёт deep-link / кнопку «Принять».
3. Accept → set password (в боте, Mini App или App) → JWT/session ready.

### B. Later (заложить в модель)

- Email invite / web magic-link → тот же `invite_tokens` table с `channel`.

## Чеклист

- [ ] Таблица invite tokens (`token`, `user_id?`, `telegram_id?`, `expires_at`, `channel`)
- [ ] Admin create + send Telegram message
- [ ] Accept endpoint / bot handler: link + password gate
- [ ] Отказ бота обслуживать unlinked `telegram_id` (сообщение «нужен инвайт / привязка»)
- [ ] Тесты: нет session insert без `user_id`

## UX note

После accept пользователь может открыть iOS App (login) или Mini App (`initData` уже = linked user).
