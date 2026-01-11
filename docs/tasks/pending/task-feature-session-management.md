# Управление сессиями

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация управления сессиями запросов: создание, завершение, отмена сессий.

## Цели

1. Реализовать создание сессий (с контекстом БЗ и без)
2. Реализовать завершение сессий
3. Реализовать отмену сессий
4. Реализовать FSM для управления сессиями
5. Реализовать проверку активной сессии

## Задачи

- [ ] Реализовать создание сессии в команде `/new_query`:
  - Создать сессию типа `query_with_kb`
  - Установить статус `active`
  - Сохранить session_id в FSM state
  - Уведомить пользователя
- [ ] Реализовать создание сессии в команде `/new_chat`:
  - Создать сессию типа `empty_chat`
  - Установить статус `active`
  - Сохранить session_id в FSM state
  - Уведомить пользователя
- [ ] Реализовать завершение сессии в команде `/end_query`:
  - Получить активную сессию пользователя
  - Обновить статус сессии на `completed`
  - Очистить FSM state
  - Уведомить пользователя
- [ ] Реализовать отмену сессии в команде `/cancel`:
  - Получить активную сессию пользователя
  - Обновить статус сессии на `cancelled`
  - Очистить FSM state
  - Уведомить пользователя
- [ ] Реализовать FSM состояния для управления сессиями:
  - `WaitingForQuery` - ожидание запроса
  - `ProcessingQuery` - обработка запроса
  - `WaitingForConfirmation` - ожидание подтверждения отката
- [ ] Реализовать проверку активной сессии перед обработкой сообщений
- [ ] Реализовать автоматическое завершение старых сессий (опционально)

## Технические детали

### Создание сессии

```python
# В handlers/commands.py
from database import DatabaseInterface
from utils.context import SessionContext

@router.message(Command("new_query"))
async def new_query_handler(message: Message, state: FSMContext):
    """Начать новый запрос с контекстом базы знаний"""
    user_id = message.from_user.id
    
    # Создать/обновить пользователя
    user = await db.ensure_user(
        telegram_id=user_id,
        username=message.from_user.username
    )
    
    # Создать сессию
    session = await db.create_session(
        user_id=user["id"],
        session_type="query_with_kb",
        status="active"
    )
    
    # Сохранить session_id в FSM state
    await state.update_data(session_id=session["id"])
    await state.set_state(QueryStates.waiting_for_query)
    
    await message.answer(
        "✅ Начат новый запрос с контекстом базы знаний.\n"
        "Отправьте ваш вопрос текстом, голосом или с файлами."
    )
```

### Завершение сессии

```python
@router.message(Command("end_query"))
async def end_query_handler(message: Message, state: FSMContext):
    """Завершить текущий запрос"""
    data = await state.get_data()
    session_id = data.get("session_id")
    
    if session_id:
        await db.update_session(
            session_id=session_id,
            status="completed"
        )
        await state.clear()
        await message.answer("✅ Запрос завершен.")
    else:
        await message.answer("❌ Нет активной сессии.")
```

## Связанные файлы

- `handlers/commands.py` - команды управления сессиями
- `handlers/states.py` - FSM состояния
- `database/base.py` - методы для работы с сессиями
- `utils/context.py` - управление контекстом сессий

