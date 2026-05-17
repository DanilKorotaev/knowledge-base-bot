# KB App API: `POST /api/query/voice` (iOS native client)

**Status:** Done — `kb_app_api/routes/voice.py`.

## Delivered

- Multipart: `session_id`, `use_knowledge_base`, `transcription_hint`, `audio` (`audio/mp4`).
- `TranscriptionService` + `QueryProcessingService.process_query_for_api`.
- Ответ `{ "messages": [...] }` (совместимо с iOS `VoiceRecordingSendResult`).

## See also

- Контракт: `knowledge-base-app-ios/docs/KB_APP_API_CONTRACT.md`
- iOS: `URLSessionKnowledgeBaseAPIClient.sendVoiceRecording`
- Чеклист деплоя: Nextcloud `Документация/Задачи/KB App API — бэкенд для iOS/Чеклист — деплой и интеграция.md`
