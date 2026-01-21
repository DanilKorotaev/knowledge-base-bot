# Система ограничения доступа к боту

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Безопасность

## Описание

Реализация системы ограничения доступа к боту для защиты личной базы знаний. Поскольку бот может быть публичным, а база знаний - личной, необходимо иметь возможность ограничить круг лиц, которые могут делать запросы к БЗ через бота.

## Проблема

В текущей реализации любой пользователь может отправить команду `/start` и начать использовать бота для работы с базой знаний. Это создает риск утечки личной информации, если бот публичный, а база знаний содержит конфиденциальные данные.

## Цели

1. Реализовать систему управления разрешенными пользователями (whitelist)
2. Реализовать проверку доступа перед обработкой запросов
3. Реализовать административные команды для управления доступом
4. Реализовать настройку режима доступа (открытый/закрытый) через конфигурацию
5. Реализовать логирование попыток доступа от неавторизованных пользователей

## Задачи

### База данных

- [ ] Добавить поле `is_allowed` в таблицу `users` (по умолчанию `false` для новых пользователей)
- [ ] Добавить поле `is_admin` в таблицу `users` (по умолчанию `false`)
- [ ] Добавить поле `access_mode` в конфигурацию (`open` / `restricted`)
- [ ] Реализовать миграцию БД для существующих пользователей (установить `is_allowed=true` для текущих пользователей)

### Интерфейс базы данных

- [ ] Добавить метод `is_user_allowed(telegram_id: int) -> bool` в `DatabaseInterface`
- [ ] Добавить метод `is_user_admin(telegram_id: int) -> bool` в `DatabaseInterface`
- [ ] Добавить метод `allow_user(telegram_id: int) -> None` в `DatabaseInterface`
- [ ] Добавить метод `disallow_user(telegram_id: int) -> None` в `DatabaseInterface`
- [ ] Добавить метод `set_user_admin(telegram_id: int, is_admin: bool) -> None` в `DatabaseInterface`
- [ ] Добавить метод `get_allowed_users() -> List[Dict]` в `DatabaseInterface`
- [ ] Реализовать все методы в `PostgreSQLDatabase`
- [ ] Реализовать все методы в `SQLiteDatabase`

### Конфигурация

- [ ] Добавить `ACCESS_MODE: str = os.getenv("ACCESS_MODE", "restricted")` в `config.py`
- [ ] Добавить `ADMIN_TELEGRAM_IDS: List[int]` в `config.py` (из переменной окружения через запятую)
- [ ] Реализовать валидацию конфигурации для режима доступа

### Middleware для проверки доступа

- [ ] Создать `middleware/access_control.py` с middleware для проверки доступа
- [ ] Реализовать проверку доступа перед обработкой всех сообщений
- [ ] Реализовать исключения для команд `/start` и `/help` (чтобы неавторизованные пользователи могли узнать о боте)
- [ ] Реализовать отправку сообщения об отказе в доступе неавторизованным пользователям
- [ ] Реализовать логирование попыток доступа от неавторизованных пользователей

### Административные команды

- [ ] Реализовать команду `/admin_allow <telegram_id>` - разрешить доступ пользователю (только для админов)
- [ ] Реализовать команду `/admin_disallow <telegram_id>` - запретить доступ пользователю (только для админов)
- [ ] Реализовать команду `/admin_list` - показать список разрешенных пользователей (только для админов)
- [ ] Реализовать команду `/admin_set_admin <telegram_id>` - назначить пользователя администратором (только для админов)
- [ ] Реализовать команду `/admin_remove_admin <telegram_id>` - убрать права администратора (только для админов)
- [ ] Реализовать проверку прав администратора перед выполнением команд
- [ ] Реализовать валидацию формата команд (проверка telegram_id)

### Обработка доступа при старте

- [ ] Модифицировать `/start` для проверки доступа
- [ ] Если режим `restricted` и пользователь не разрешен - показать сообщение об отказе
- [ ] Если режим `restricted` и пользователь разрешен - показать обычное приветствие
- [ ] Если режим `open` - разрешить всем (текущее поведение)
- [ ] Автоматически добавлять администраторов из конфигурации в список разрешенных при первом запуске

### Документация

- [ ] Обновить `docs/SETUP.md` с описанием настройки доступа
- [ ] Добавить описание переменных окружения `ACCESS_MODE` и `ADMIN_TELEGRAM_IDS`
- [ ] Добавить примеры использования административных команд
- [ ] Обновить `README.md` с информацией о системе доступа

## Технические детали

### Режимы доступа

- **`open`** - открытый режим, все пользователи имеют доступ (текущее поведение)
- **`restricted`** - ограниченный режим, только пользователи из whitelist имеют доступ

### Структура таблицы users

```sql
ALTER TABLE users ADD COLUMN is_allowed BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE;
```

### Пример middleware

```python
# В middleware/access_control.py
from aiogram import BaseMiddleware
from aiogram.types import Message
from config import config
from utils.db_helpers import get_db

class AccessControlMiddleware(BaseMiddleware):
    """Middleware для проверки доступа пользователей"""
    
    async def __call__(self, handler, event: Message, data):
        # Если режим открытый - пропускаем всех
        if config.ACCESS_MODE == "open":
            return await handler(event, data)
        
        # Разрешенные команды для всех (даже неавторизованных)
        allowed_commands = ["/start", "/help"]
        if event.text and any(event.text.startswith(cmd) for cmd in allowed_commands):
            return await handler(event, data)
        
        # Проверка доступа
        db = await get_db()
        user_id = event.from_user.id
        
        if not await db.is_user_allowed(user_id):
            await event.answer(
                "❌ У вас нет доступа к этому боту.\n\n"
                "Обратитесь к администратору для получения доступа."
            )
            logger.warning(f"Попытка доступа от неавторизованного пользователя: {user_id}")
            return
        
        return await handler(event, data)
```

### Пример административных команд

```python
# В handlers/commands.py
@router.message(Command("admin_allow"))
async def admin_allow_handler(message: Message):
    """Разрешить доступ пользователю"""
    db = await get_db()
    user_id = message.from_user.id
    
    # Проверка прав администратора
    if not await db.is_user_admin(user_id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    # Получить telegram_id из команды
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer("❌ Использование: /admin_allow <telegram_id>")
        return
    
    try:
        target_telegram_id = int(command_parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат telegram_id.")
        return
    
    # Разрешить доступ
    await db.allow_user(target_telegram_id)
    await message.answer(f"✅ Пользователю {target_telegram_id} разрешен доступ.")
```

### Переменные окружения

```bash
# Режим доступа: "open" или "restricted"
ACCESS_MODE=restricted

# Список администраторов (через запятую)
ADMIN_TELEGRAM_IDS=123456789,987654321
```

## Связанные файлы

- `middleware/access_control.py` - middleware для проверки доступа (новый файл)
- `database/base.py` - интерфейс методов для работы с доступом
- `database/postgresql_db.py` - реализация для PostgreSQL
- `database/sqlite_db.py` - реализация для SQLite
- `config.py` - настройки режима доступа
- `handlers/commands.py` - административные команды
- `bot.py` - регистрация middleware
- `docs/SETUP.md` - документация по настройке

## Безопасность

1. **По умолчанию закрыто**: Режим доступа по умолчанию должен быть `restricted`
2. **Администраторы из конфигурации**: Администраторы из `ADMIN_TELEGRAM_IDS` автоматически получают доступ при первом запуске
3. **Логирование**: Все попытки доступа от неавторизованных пользователей должны логироваться
4. **Валидация**: Проверка прав администратора перед выполнением административных команд
5. **Миграция**: Существующие пользователи должны быть явно добавлены в whitelist администратором

## Миграция существующих данных

При первом запуске с новой версией:
- Если `ACCESS_MODE=restricted` и есть существующие пользователи - они должны быть явно добавлены администратором
- Администраторы из `ADMIN_TELEGRAM_IDS` автоматически получают `is_allowed=true` и `is_admin=true`

