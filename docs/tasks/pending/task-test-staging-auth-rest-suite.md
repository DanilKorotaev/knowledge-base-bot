# Test: REST / smoke suite на staging

**Статус:** ✅ Done (скрипт; CI job опционально)  
**Приоритет:** 🟡 Средний  
**Категория:** Testing  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** auth на staging

## Цель

Живые HTTP-проверки против `https://kbapp-staging.example.com` после CI deploy staging (или workflow_dispatch):

- health
- register/login/refresh/me (когда auth готов)
- sessions isolations между двумя users
- devices register scoped to user

До auth: suite может логиниться старым способом только на staging transitional — после remove Bearer только login.

## Чеклист

- [x] Скрипт `scripts/staging_auth_smoke.sh` (`BASE_URL=…`)
- [x] Secrets: не нужны — создаёт временных users
- [ ] Опционально job после `deploy-mac-mini-staging.yml`
- [x] Прогон на staging localhost:8191 (2026-10-25) — OK
