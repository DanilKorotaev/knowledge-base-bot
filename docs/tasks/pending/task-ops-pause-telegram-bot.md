# Ops: pause Telegram bot (multi-user era)

**Статус:** 📋 Planned (host pause **отложена** 2026-10-26 — сначала доки/эпик; runtime можно оставить)  
**Приоритет:** 🟢 Low  
**Категория:** Ops / Telegram  
**Эпик:** [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)

## Цель

Пока Telegram не умеет multi-user App identity, при желании **не держать бота в проде** как рабочий канал. Сейчас пользователь им не пользуется; пауза на host — optional, не блокер.

## Чеклист

- [ ] Host / compose: не стартовать `bot` (или `TELEGRAM_BOT_ENABLED=false` / profile `telegram`)
- [ ] Staging: то же, если бот ещё крутится
- [ ] Mini App контейнер: остановить или оставить read-only static без webhook (решение в задаче)
- [ ] В [README](../../README.md) / ops-доках: статус **deprecated / paused**, ссылка на эпик (см. doc-задачи)
- [ ] CI/alerts: не падать из‑за остановленного бота; Telegram notifications для CI — оставить (notifications-only)

## Не делать здесь

- Удаление кода бота / miniapp
- Переписывание handlers под multi-user (это другие подзадачи эпика)
