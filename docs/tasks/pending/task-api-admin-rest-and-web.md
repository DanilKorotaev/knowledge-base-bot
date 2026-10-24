# API + Admin web (не Telegram)

**Статус:** 🚧 MVP на staging (`dbee382`) — UI `/admin/`, DNS готов; nginx на VPS — вручную  
**Приоритет:** 🟡 Высокий после auth  
**Категория:** Admin  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** `task-api-auth-nextcloud-users`

## Цель

Отдельная **веб-админка** + Admin REST. Без miniapp / Telegram.

## Admin REST (role=admin)

- List/create/disable users
- Invite: temp password → email; `must_change_password`
- Set `quota_bytes`, `cursor_isolation`
- Resend invite / reset password (→ NC)
- Later: provider keys CRUD (`task-api-instance-settings-provider-keys`)

## Admin web

- Отдельный фронт в репо (например `admin-web/`) или static service в compose
- Логин admin JWT против того же API
- Домены (DNS + nginx на VPS — создать когда UI готов):
  - staging: `https://kbadmin-staging.coredan.ru`
  - prod: `https://kbadmin.coredan.ru`

## Чеклист

- [x] Admin routes + authz (`/api/admin/users`)
- [ ] Email send (invite) — SMTP/settings
- [x] Scaffold admin-web (`admin-web/` → `/admin/`)
- [x] Staging: UI отдаётся с `:8191/admin/` (200)
- [ ] VPS nginx+TLS для `kbadmin-staging` (конфиг в vault; нужен sudo на vpn-new)
- [ ] Prod `kbadmin` — только после merge в `main`
