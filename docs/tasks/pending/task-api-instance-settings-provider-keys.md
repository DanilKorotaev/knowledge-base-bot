# API: instance settings + provider keys (не только env)

**Статус:** 📋 Planned  
**Приоритет:** 🟢 Средний / later  
**Категория:** Admin / Config  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** `task-api-admin-rest-and-web`

## Цель

Динамические настройки инстанса и ключи Cursor / других провайдеров в БД (шифр at-rest), управляемые из админки. Env — только bootstrap (первый admin, encryption key, DB).

## Чеклист

- [ ] Таблица `instance_settings` / `provider_credentials`
- [ ] Admin CRUD UI + API
- [ ] Runtime читает ключи для Cursor/OpenAI из settings с fallback на env на переходный период
- [ ] Документация self-host: «ключи в админке»
