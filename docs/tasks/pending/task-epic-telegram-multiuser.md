# Epic: Telegram multi-user (link + invite + bot)

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний (после стабилизации KB App API)  
**Категория:** Telegram / Auth  
**Связь:** из README/доков — единственная ссылка на «воскрешение Telegram»

## Контекст

KB App API уже multi-user (JWT, per-user vault). Legacy Telegram-бот и Mini App заточены под `telegram_id` как primary identity. Пока бот **не нужен в проде** — см. [пауза бота](task-ops-pause-telegram-bot.md). Этот эпик — план вернуть Telegram как **вторичный канал** того же App-user.

## Решения (зафиксировано 2026-10-26)

- **1 App user ↔ 1 Telegram** (никаких one-to-many).
- Пока бот/мини-ап **paused / deprecated** в доках; runtime можно не поднимать.
- **Инвайт без пароля** через Telegram в v1; email/magic-link — later, но модель не должна мешать.
- При принятии инвайта сразу: создать/активировать App-user + записать `telegram_id` → **нет orphan-сессий** «голый telegram_id».
- Cursor channel `telegram`: явно «отвечай под Telegram Markdown».
- Web (Mini App / mobile web / desktop) — отдельный эпик [task-epic-web-kb-clients.md](task-epic-web-kb-clients.md); Mini App auth через `initData` → тот же linked user.

## Подзадачи

| Порядок | Задача |
|--------|--------|
| 0 | [Pause Telegram bot runtime](task-ops-pause-telegram-bot.md) |
| 1 | [1:1 link model + API](task-api-telegram-account-link-1to1.md) |
| 2 | [Invite without password via Telegram](task-feature-telegram-invite-no-password.md) |
| 3 | [Bot resolves `user_id`, sessions as App](task-feature-telegram-bot-user-scoped.md) |
| 4 | [Channel prompt + Markdown fidelity](task-feature-telegram-markdown-and-channel.md) |
| 5 | Mini App → см. web-эпик (initData auth) |

## Вне скоупа этого эпика

- Android native
- Полный parity Health Sync в web
- Отдельный git-репозиторий только для бота (обсудить позже)

## Definition of done (эпик)

- [ ] Документация ссылается сюда как на единственный Epic Telegram revival
- [ ] Все подзадачи в таблице закрыты или явно отменены
- [ ] Нет пути создания сессий без App `user_id`
