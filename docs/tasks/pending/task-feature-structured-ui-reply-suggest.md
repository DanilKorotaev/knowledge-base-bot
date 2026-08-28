# Feature: Organic Structured UI in normal chat replies

**Status:** pending  
**Vault:** `Документация/Задачи/task-structured-ui-next.md` §2B

## Problem

Тоггл Interactive UI On на клиенте задаёт ожидание: **любой** уместный вопрос ассистента — с кнопками/формой, без ручного «старт» в toolbar.

Сейчас работает цепочка `reply_suggest.py` после текстового ответа, но:

- промпт консервативен (`Do not attach when the reply is already a complete answer`);
- список нод в `_PROMPT` устарел (нет P2/P3);
- основной чат-агент не координируется с SUI (сначала текст, потом второй проход).

## Done when

- [ ] Обновить `_PROMPT`: полный schema v1, anti-meta, короткие labels
- [ ] Явно attach при вопросе с вариантами («что берём?», «выбери приоритет»), даже если в тексте уже перечислены опции
- [ ] Не требовать ручной `ui-events` start для типичного выбора
- [ ] Тесты на suggest (mock LLM): вопрос → screen с кнопками; чистый ответ → `null`
- [ ] Док: §2B в vault актуален

## Out of scope

- Reminders-логика в `structured_ui_agent_prompt.md` (только общая схема)
- Личные URL в промптах

## References

- `kb_app_api/structured_ui/reply_suggest.py`
- `kb_app_api/tests/test_structured_ui_reply_suggest.py`
