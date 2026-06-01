# KB App API: вложения, голос, формат контента в сообщениях

**Статус:** ✅ Выполнено  
**Приоритет:** 🟠 Высокий  
**Категория:** KB App API  
**Дата завершения:** 2026-06-01  
**iOS:** [task-ux-chat-rich-messages.md](../../../knowledge-base-app-ios/docs/tasks/completed/task-ux-chat-rich-messages.md)  
**Контракт:** `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`

## Реализовано

- `message_to_kb` / `messages_to_kb` + `enrich_session_messages` — batch attachments и transcriptions.
- `GET /api/sessions/{session_id}/attachments/{attachment_id}/file` — локальный файл или прокси Telegram (auth + ownership).
- Поля `content_format` (`markdown` | `html` | `plain`), `attachments[]`, `transcription` на сообщении для voice.
- `POST /api/query/voice` возвращает enriched messages.
- Unit-тесты: `kb_app_api/tests/test_serializers.py`, расширен `test_smoke.py`.

## Файлы

- `kb_app_api/serializers.py`, `kb_app_api/message_enrichment.py`
- `kb_app_api/routes/attachments.py`, `kb_app_api/routes/messages.py`, `kb_app_api/routes/voice.py`

## Acceptance

- [x] iOS может отобразить фото и проиграть голос из истории без Telegram.
- [x] Транскрипция voice доступна в JSON.
- [x] Assistant markdown не экранируется лишний раз; при `content_format=html` клиент может рендерить HTML.
