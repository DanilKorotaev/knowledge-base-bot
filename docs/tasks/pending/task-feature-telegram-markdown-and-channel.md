# Feature: Telegram Markdown + Cursor channel fidelity

**Статус:** 📋 Planned  
**Приоритет:** 🟢 Low / after bot multi-user  
**Категория:** Telegram / Agent  
**Эпик:** [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)  
**Depends on:** [task-feature-telegram-bot-user-scoped.md](task-feature-telegram-bot-user-scoped.md)

## Цель

1. В Cursor уходит явный channel = Telegram (`agent/channel_telegram_prompt.md` + runtime flag) — «я через Telegram, отвечай так».
2. Исходящие сообщения в Telegram корректно сохраняют/рендерят форматирование (то, что уже есть в message store / rich content).
3. Mini App / web chat показывают тот же Markdown, что App (актуализировать рендерер).

## Чеклист

- [ ] Query pipeline всегда передаёт channel hint для TG
- [ ] Аудит round-trip: agent Markdown → Telegram parse mode / entities → DB → Mini App render
- [ ] Известные поломки `.md` path autolink и т.п. — регрессия не вернуть
- [ ] Согласовать с iOS Structured UI / markdown (где пересекается)

## Связь

- Web chat render: [task-epic-web-kb-clients.md](task-epic-web-kb-clients.md)
