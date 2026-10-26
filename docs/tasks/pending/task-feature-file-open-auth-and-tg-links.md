# Feature: file open auth (iOS) + Telegram Mini App links

**Статус:** 📋 Planned (from session 299 ideas, 2026-10-26)  
**Приоритет:** 🟡 Средний  
**Категория:** KB App / Telegram revival

## Контекст

Автосоздание **публичных** Nextcloud share-ссылок при изменении файлов Cursor — отключено (legacy для Telegram WebView). Явный `POST /api/files/share-link` остаётся.

## Что ещё нужно (не сейчас)

1. **Telegram (когда revival):** в списке изменённых файлов ссылка → Mini App (уже авторизованный контекст), а не публичный NC share / голый NC URL.
2. **iOS «Открыть здесь» (WKWebView/модалка):** прокинуть сессию App Password / cookie / token в in-app NC viewer, чтобы не логиниться руками. «Открыть в Nextcloud / Safari» уже ок (системная авторизация пользователя).
3. Продумать UX + threat model (не светить App Password в WebView URL).

## Related

- `POST /api/files/open-link`, `POST /api/files/share-link`
- [task-ux-clickable-file-links-in-response.md](task-ux-clickable-file-links-in-response.md)
- [task-epic-telegram-multiuser.md](task-epic-telegram-multiuser.md)
