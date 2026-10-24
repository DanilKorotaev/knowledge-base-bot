# Test: REST / smoke suite на staging

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний  
**Категория:** Testing  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** auth на staging

## Цель

Живые HTTP-проверки против `https://kbapp-staging.coredan.ru` после CI deploy staging (или workflow_dispatch):

- health
- register/login/refresh/me (когда auth готов)
- sessions isolations между двумя users
- devices register scoped to user

До auth: suite может логиниться старым способом только на staging transitional — после remove Bearer только login.

## Чеклист

- [ ] Скрипт или pytest marker `staging_live`
- [ ] Secrets: staging test user (не в git)
- [ ] Опционально job после `deploy-mac-mini-staging.yml`
- [ ] Документ в `docs/testing/` или E2E notes
