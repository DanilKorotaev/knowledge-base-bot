# Epic: Web KB clients (Mini App + mobile web + desktop)

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний (после / параллельно поздним Telegram-задачам)  
**Категория:** Web / Product  
**Связь:** Telegram Mini App auth → [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)

## Цель

Один продукт-поверхность в трёх оболочках:

| Оболочка | Auth | UX |
|----------|------|-----|
| Telegram Mini App | `initData` → linked App user | mobile-like |
| Mobile web | login / password (+ multi-account) | mobile-like |
| Desktop web | login / password (+ multi-account) | desktop layout |

Общий код (один фронт), разные entry/auth adapters. Функциональность ≈ iOS App без Health Sync: **сессии, composer (текст/голос/аттачи), Structured UI, boards/actions**, push optional.

## Capability matrix (заложить)

- Каталог capabilities: `ios | miniapp | mobile_web | desktop_web`
- Structured UI / boards: если capability недоступна на канале — **не ломать UI**: скрыть или показать «недоступно здесь»
- Offline cache на web — optional / later

## Подзадачи (дробление по мере уточнения архитектуры)

- [ ] Spike: один SPA (React/Vue/…) vs эволюция текущего `miniapp/static`
- [ ] Auth adapters: initData vs JWT login; multi-account store на web
- [ ] Sessions list + chat + composer parity
- [ ] Boards / Actions / Structured UI host
- [ ] Markdown / rich message render (общий с Mini App)
- [ ] Deploy: static hosting + API CORS; Mini App URL vs public web URL

## Решения пока

- Не отдельный репозиторий (сначала папка в monorepo; split repo — отдельное обсуждение).
- Android native — вне скоупа.

## Definition of done (эпик)

- [ ] Три оболочки открывают одни и те же сессии того же App-user
- [ ] Mini App не создаёт orphan users
- [ ] Документация web лежит рядом с KB App API docs (не в legacy Telegram-only)
