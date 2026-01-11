# Обработка текстовых сообщений

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация обработки текстовых сообщений от пользователей с интеграцией Cursor CLI для работы с базой знаний.

## Цели

1. Реализовать обработку текстовых сообщений в активной сессии
2. Интегрировать с Cursor CLI для обработки запросов
3. Реализовать отслеживание изменений файлов
4. Реализовать синхронизацию изменений с NextCloud

## Задачи

- [ ] Реализовать получение активной сессии пользователя
- [ ] Реализовать добавление сообщения пользователя в историю сессии
- [ ] Реализовать проверку типа сессии (с контекстом базы знаний или без)
- [ ] Реализовать сохранение состояния файлов перед обработкой (для отслеживания изменений)
- [ ] Реализовать вызов Cursor CLI через `cursor_cli_service.process_query()`
- [ ] Реализовать получение ответа от Cursor CLI и списка изменений файлов
- [ ] Реализовать отслеживание изменений в БД через `change_tracker`
- [ ] Реализовать отправку ответа пользователю с форматированием Markdown
- [ ] Реализовать сохранение обоих сообщений (пользователя и ассистента) в БД
- [ ] Реализовать синхронизацию изменений с NextCloud (если были изменения)
- [ ] Реализовать обработку ошибок и таймаутов
- [ ] Реализовать разбиение длинных ответов на части (если превышает лимит Telegram)
- [ ] Обработать случай отсутствия активной сессии (предложить создать новую)
- [ ] Реализовать обработку команд в текстовых сообщениях (если сообщение начинается с `/`)

## Логика обработки

1. Получить активную сессию пользователя
2. Добавить сообщение пользователя в историю сессии
3. Если сессия с контекстом базы знаний:
   - Сохранить состояние файлов (для отслеживания изменений)
   - Вызвать Cursor CLI через `cursor_cli_service.process_query()`:
     - Cursor CLI автоматически загружает системные промпты из `.cursor/rules/`
     - Cursor CLI видит все файлы в директории локальной копии
     - Cursor CLI может читать, искать и изменять файлы
     - Использует настроенный API ключ (CURSOR_API_KEY или OPENAI_API_KEY)
4. Получить ответ от Cursor CLI и список изменений файлов
5. Отследить изменения в БД (через change_tracker)
6. Отправить ответ пользователю (с форматированием Markdown)
7. Сохранить оба сообщения в БД
8. Синхронизировать изменения с NextCloud (если были изменения)

## Технические детали

### Интеграция с Cursor CLI

```python
# В handlers/messages.py
from services.cursor_cli_service import CursorCLIService
from services.change_tracker import ChangeTracker
from services.sync_service import SyncService

async def process_text_message(message: Message, state: FSMContext):
    # Получить активную сессию
    session = await db.get_active_session(user_id)
    
    # Сохранить состояние файлов
    file_states = await change_tracker.save_file_states(session_id)
    
    # Вызвать Cursor CLI
    cursor_service = CursorCLIService(kb_path=config.LOCAL_KB_PATH)
    response, changes = await cursor_service.process_query(
        query=message.text,
        session_id=session["id"]
    )
    
    # Отследить изменения
    for change in changes:
        await change_tracker.track_file_change(
            session_id=session["id"],
            file_path=change["path"],
            change_type=change["type"],
            old_content=change.get("old_content"),
            new_content=change.get("new_content")
        )
    
    # Синхронизировать с NextCloud
    if changes:
        await sync_service.sync_to_nextcloud()
    
    # Отправить ответ
    await message.answer(response, parse_mode="Markdown")
```

## Связанные файлы

- `handlers/messages.py` - основной обработчик
- `services/cursor_cli_service.py` - интеграция с Cursor CLI
- `services/change_tracker.py` - отслеживание изменений
- `services/sync_service.py` - синхронизация с NextCloud
- `utils/message_helpers.py` - помощники для работы с сообщениями
- `utils/context.py` - управление контекстом сессий

