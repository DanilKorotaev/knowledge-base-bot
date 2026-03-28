# Руководство для разработчиков

## Структура проекта

```
knowledge-base-bot/
├── bot.py                      # Точка входа
├── config.py                   # Конфигурация
├── database/                   # Работа с БД
│   ├── base.py                 # Интерфейс DatabaseInterface
│   ├── postgresql_db.py        # Реализация PostgreSQL
│   └── sqlite_db.py            # Реализация SQLite
├── services/                    # Бизнес-логика (сервисы)
│   ├── query_processing_service.py  # Обработка запросов пользователей
│   ├── session_service.py           # Управление сессиями
│   ├── sync_service.py              # Синхронизация с NextCloud
│   ├── cursor_cli_service.py        # Работа с Cursor CLI
│   ├── openai_service.py            # Работа с OpenAI API
│   └── transcription_service.py     # Транскрибация голосовых
├── handlers/                    # Обработчики Telegram
│   ├── commands.py             # Команды бота
│   ├── messages.py              # Текстовые сообщения
│   ├── voice.py                 # Голосовые сообщения
│   ├── callbacks.py             # Inline-кнопки
│   └── media.py                 # Медиа-файлы
├── middleware/                  # Middleware и декораторы
│   ├── access_control.py        # Контроль доступа
│   └── admin_middleware.py      # Декоратор @require_admin
└── utils/                       # Утилиты
    ├── constants.py             # Константы проекта
    ├── error_helpers.py         # Обработка ошибок
    ├── session_helpers.py      # Утилиты для сессий
    ├── message_helpers.py       # Утилиты для сообщений
    ├── telegram_helpers.py      # Утилиты для Telegram API
    └── ...
```

## Разработка

### Локальная разработка

1. Используйте SQLite для локальной разработки:
```bash
DB_TYPE=sqlite
DB_FILE=bot.db
```

2. Отключите синхронизацию с NextCloud:
```bash
ENABLE_SYNC=false
```

3. Укажите путь к локальной копии базы знаний:
```bash
LOCAL_KB_PATH=/path/to/your/local/knowledge-base
```

### Долгие запросы: UX и таймауты Cursor CLI

Пока `cursor-agent` обрабатывает запрос, бот показывает статус с таймером, меткой сессии (`· #id`) и кнопкой «Отменить». После первого чанка стрима текст переключается на «Получаю ответ…» (если включён `STREAMING_ENABLED`).

| Переменная (окружение) | По умолчанию | Смысл |
|------------------------|--------------|--------|
| `QUERY_PROGRESS_TIMER_INTERVAL` | `15` | Интервал в секундах между обновлениями текста статуса. |
| `CURSOR_CLI_TIMEOUT` | `600` | Секунд **одного** ожидания вывода **до первого непустого чанка** в stdout. Это не «общий лимит на весь ответ»; для тяжёлых задач без вывода в поток оставляйте **600+** или задавайте явно. |
| `CURSOR_CLI_IDLE_TIMEOUT` | `30` | После первого чанка — максимум секунд **тишины между чанками** stdout; затем чтение завершается и процесс корректно закрывается. |

Не уменьшайте `CURSOR_CLI_TIMEOUT` «для всех» без причины — иначе выше риск оборвать долгое размышление модели без вывода.

Шаблон переменных: `.env.example`. Поведение при нескольких параллельных сессиях зафиксировано в `docs/tasks/completed/task-ux-long-query-feedback.md`.

### Добавление новых функций

1. **Новые команды**: Добавьте в `handlers/commands.py`
2. **Новые сервисы**: Создайте в `services/`
3. **Новые утилиты**: Добавьте в `utils/`

### Использование сервисов

#### Обработка запросов

```python
from services.query_processing_service import QueryProcessingService
from services.session_service import SessionService
from utils.constants import SessionType

# Получить или создать сессию
session_service = SessionService()
active_session = await session_service.get_or_create_active_session(
    user_id=user_id,
    username=username,
    session_type=SessionType.QUERY_WITH_KB
)

# Обработать запрос
query_service = QueryProcessingService()
await query_service.process_query(
    query=query,
    session_id=active_session["id"],
    message=message
)
```

#### Административные обработчики

```python
from middleware.admin_middleware import require_admin

@router.callback_query(lambda c: c.data == "admin_action")
@require_admin
async def admin_handler(callback: CallbackQuery):
    # Код обработчика
    pass
```

#### Обработка ошибок

```python
from utils.error_helpers import send_error_message, handle_error_silently

try:
    # Код обработчика
    pass
except Exception as e:
    await send_error_message(
        event=message,
        error=e,
        user_message="❌ Произошла ошибка",
        log_message="Ошибка в обработчике"
    )
```

### Лучшие практики

1. **Используйте сервисы вместо прямой работы с БД:**
   - ❌ `db = await get_db(); session = await db.create_session(...)`
   - ✅ `session_service = SessionService(); session = await session_service.create_new_session(...)`

2. **Используйте декоратор для административных действий:**
   - ❌ `if not await db.is_user_admin(user_id): return`
   - ✅ `@require_admin`

3. **Используйте стандартизированную обработку ошибок:**
   - ❌ Разные подходы к обработке ошибок в разных местах
   - ✅ `send_error_message()` или `handle_error_silently()`

4. **Используйте константы вместо магических строк:**
   - ❌ `session_type="query_with_kb"`
   - ✅ `session_type=SessionType.QUERY_WITH_KB`

5. **Упорядочивайте импорты согласно PEP 8:**
   - Стандартная библиотека
   - Пустая строка
   - Сторонние библиотеки
   - Пустая строка
   - Локальные импорты

### Тестирование

```bash
# Запуск бота в режиме разработки
python bot.py
```

## Стиль кода

- Используйте type hints
- Следуйте PEP 8
- Документируйте функции и классы
- Используйте логирование вместо print

## Git workflow

1. Создайте feature branch
2. Внесите изменения
3. Создайте pull request
4. После ревью - merge в main

