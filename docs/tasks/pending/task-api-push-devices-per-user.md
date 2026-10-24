# API/iOS: push devices после multi-user auth

**Статус:** 📋 Planned  
**Приоритет:** 🟡 Средний (после auth)  
**Категория:** Push  
**Эпик:** vault `эпик-kb-app-avtorizaciya-multiuser`  
**Depends on:** `task-api-auth-nextcloud-users`

## Контекст

`POST /api/devices` уже пишет `user_id` через `get_api_user` + `upsert_user_device`. После замены shared Bearer на JWT это станет per-real-user автоматически — нужно проверить и закрыть дыры.

## Чеклист

- [ ] Register/unregister только с access token юзера
- [ ] `notify_chat_reply_ready` шлёт только на devices владельца сессии
- [ ] Logout: опционально unregister текущего device / revoke sessions
- [ ] iOS: register APNs **после** login; unregister на logout (см. iOS task)
- [ ] Staging smoke: два юзера — push не пересекаются
