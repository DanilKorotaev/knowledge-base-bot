# API: Telegram ↔ App user link (1:1)

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** kb_app_api / Auth  
**Эпик:** [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)  
**Depends on:** стабильный JWT auth (`task-api-auth-nextcloud-users`)

## Цель

Жёсткая связь **один** `users.id` ↔ **один** `users.telegram_id` (UNIQUE, nullable until linked).

## Модель

- `users.telegram_id` UNIQUE NULL (уже почти так; добить миграции/индексы)
- Запрет: второй App-user не может привязать занятый `telegram_id`
- Запрет: один App-user не держит два telegram id
- Unlink (optional later): обнулить `telegram_id`, сессии остаются у `user_id`

## API (черновик)

- `POST /api/auth/telegram/link` — из App: подтверждение кодом / deep-link token
- `DELETE /api/auth/telegram/link` — unlink (v2?)
- `GET /api/auth/me` — уже отдаёт / добавить `telegram_id` / `telegram_linked: bool`
- Internal: resolve `telegram_id → user` для бота и Mini App

## Чеклист

- [ ] Миграции + UNIQUE + тесты конфликтов
- [ ] Link flow token (одноразовый, TTL)
- [ ] Settings iOS: «Привязать Telegram» (отдельная iOS-задача или подпункт)
- [ ] Нет `ensure_user(telegram_id)` без App-user в новых путях

## Later (заложить, не реализовывать)

- Link через email magic-link / web settings
