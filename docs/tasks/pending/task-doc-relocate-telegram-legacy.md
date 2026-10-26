# Doc: relocate Telegram + Mini App docs to legacy folder

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** Documentation  
**Эпик:** [task-epic-documentation-refresh.md](task-epic-documentation-refresh.md)  
**Depends on:** [task-doc-readme-kb-app-primary.md](task-doc-readme-kb-app-primary.md) (хотя бы черновик статуса)

## Что хотим добиться

Не потерять описание бота/Mini App/фич Telegram, но **не смешивать** с KB App API.

Предлагаемый layout:

```
docs/telegram/           # legacy channel
  README.md              # deprecated banner + link to epic-telegram-multiuser
  MINIAPP.md             # из docs/MINIAPP.md
  ARCHITECTURE_BOT.md    # выжимка старой bot-схемы из ARCHITECTURE
  SETUP_NOTES.md         # выжимки из SETUP*, Nextcloud bot share
```

Корневые `docs/MINIAPP.md` и бот-центричные куски → move + stub-redirect («перенесено в…»).

## Чеклист

- [ ] Создать `docs/telegram/` + banner Deprecated
- [ ] Перенести / разрезать файлы без потери ссылок из `completed` tasks (обновить пути или оставить stubs)
- [ ] `docs/README.md` — секция Legacy
- [ ] Не тащить туда KB App contract / boards / auth JWT

## Out of scope

- Отдельный git-репозиторий для бота (отдельное решение)
- Правка кода miniapp
