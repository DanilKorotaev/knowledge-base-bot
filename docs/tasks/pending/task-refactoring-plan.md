# План рефакторинга Knowledge Base Bot

## Дата создания
2024-12-19

## Текущий статус
🟢 **Фаза 1, Фаза 2, Фаза 3 и частично Фаза 4 завершены** (2025-01-22)

### Выполнено:
- ✅ Созданы все утилиты и константы (Фаза 1)
- ✅ Созданы все сервисы (Фаза 2)
- ✅ Рефакторинг handlers завершен (Фаза 3)
  - ✅ Рефакторинг `handlers/messages.py`
  - ✅ Рефакторинг `handlers/voice.py`
  - ✅ Рефакторинг `handlers/callbacks.py`
  - ✅ Рефакторинг `handlers/commands.py`
- ✅ Частично Фаза 4: Создан декоратор `@require_admin`
  - ✅ Создан `middleware/admin_middleware.py` с декоратором `@require_admin`
  - ✅ Применен ко всем административным обработчикам (11+ обработчиков)
  - ✅ Устранено дублирование проверки прав администратора

### Следующие шаги:
1. Фаза 4: Завершить улучшения (стандартизация ошибок, оптимизация импортов)
2. Фаза 5: Тестирование

## Цель
Устранить дублирование кода, улучшить архитектуру и соблюдение принципов SOLID, DRY, KISS.

---

## Анализ проблем

### 1. Критическое дублирование кода

#### 1.1. Обработка запросов (DRY нарушение)
**Проблема:** Логика обработки запросов дублируется в `messages.py` и `voice.py`

**Дублирующийся код:**
- `process_final_query()` в `messages.py` (строки 29-186)
- `process_text_query_after_transcription()` в `voice.py` (строки 32-182)

**Что дублируется:**
- Получение истории сессии
- Синхронизация с NextCloud
- Вызов Cursor CLI
- Форматирование и отправка ответа
- Обработка изменений файлов
- Сохранение сообщений в БД

**Решение:** Вынести в общий сервис `QueryProcessingService`

---

#### 1.2. Управление сессиями (DRY нарушение)
**Проблема:** Логика создания/получения сессий дублируется в 4 файлах

**Дублирующийся код:**
- `messages.py`: строки 264-278, 407-421
- `voice.py`: строки 255-269
- `callbacks.py`: строки 57-70, 264-278, и др.
- `commands.py`: строки 117-133, 161-172, 238-257

**Что дублируется:**
```python
db = await get_db()
user = await db.ensure_user(user_id, username)
active_session = await db.get_active_session(user["id"])
if not active_session:
    active_session = await db.create_session(...)
```

**Решение:** Создать `SessionService` с методами:
- `get_or_create_active_session(user_id, session_type)`
- `ensure_user_session(user_id, username)`

---

#### 1.3. Форматирование ответов (DRY нарушение)
**Проблема:** Логика форматирования и отправки ответов дублируется

**Дублирующийся код:**
- `messages.py`: строки 109-122
- `voice.py`: строки 107-120

**Что дублируется:**
- Разбиение длинных сообщений
- Попытка HTML форматирования
- Fallback на Markdown V2
- Fallback на plain text

**Решение:** Вынести в `utils/message_helpers.py`:
- `send_formatted_message(message, text, reply_markup=None)`

---

#### 1.4. Обработка изменений файлов (DRY нарушение)
**Проблема:** Логика обработки изменений файлов дублируется

**Дублирующийся код:**
- `messages.py`: строки 131-159
- `voice.py`: строки 126-165

**Что дублируется:**
- Логирование изменений в БД
- Синхронизация с NextCloud
- Форматирование информации об изменениях
- Отправка сообщения с изменениями

**Решение:** Вынести в `QueryProcessingService`:
- `handle_file_changes(session_id, changes, message)`

---

#### 1.5. Синхронизация с NextCloud (DRY нарушение)
**Проблема:** Логика синхронизации дублируется в 4 местах

**Дублирующийся код:**
- `messages.py`: строки 60-85
- `voice.py`: строки 59-84
- `callbacks.py`: строки 891-1003
- `commands.py`: строки 847-958

**Что дублируется:**
- Проверка включена ли синхронизация
- Callback для уведомлений
- Вызов `sync_from_nextcloud()`
- Обработка прогресса синхронизации
- Обработка Flood control

**Решение:** Улучшить `SyncService`:
- Добавить метод `sync_with_progress(message, show_notification=True)`
- Вынести логику прогресса в отдельный метод

---

#### 1.6. Форматирование списка сессий (DRY нарушение)
**Проблема:** Логика форматирования списка сессий дублируется

**Дублирующийся код:**
- `callbacks.py`: строки 429-484, 827-872
- `commands.py`: строки 400-449

**Что дублируется:**
- Получение сессий пользователя
- Фильтрация удаленных сессий
- Поиск активной сессии
- Форматирование списка
- Пагинация

**Решение:** Вынести в `utils/session_helpers.py`:
- `format_sessions_list(sessions, active_session_id, page=0, per_page=5)`
- `get_user_sessions_for_display(user_id, page=0)`

---

#### 1.7. Административные проверки (DRY нарушение)
**Проблема:** Проверка прав администратора дублируется

**Дублирующийся код:**
- `callbacks.py`: множество обработчиков `admin_*`
- `commands.py`: строки 580-831

**Что дублируется:**
```python
if not await db.is_user_admin(user_id):
    await callback.answer("❌ У вас нет прав администратора.", show_alert=True)
    return
```

**Решение:** Создать декоратор или middleware:
- `@require_admin` декоратор
- Или middleware `AdminMiddleware`

---

### 2. Нарушения принципов SOLID

#### 2.1. Single Responsibility Principle (SRP)
**Проблема:** Handlers содержат бизнес-логику

**Примеры:**
- `messages.py`: содержит логику обработки запросов, синхронизации, форматирования
- `voice.py`: содержит логику транскрибации, обработки запросов, синхронизации
- `callbacks.py`: содержит логику управления сессиями, административные действия

**Решение:** 
- Вынести бизнес-логику в сервисы
- Handlers должны только координировать вызовы сервисов

---

#### 2.2. Open/Closed Principle (OCP)
**Проблема:** Сложно расширять функциональность без изменения существующего кода

**Примеры:**
- Добавление нового типа обработки запросов требует изменения множества мест
- Добавление нового типа медиа требует изменения QueryBuilder и всех обработчиков

**Решение:**
- Использовать стратегии для обработки разных типов запросов
- Использовать фабрики для создания обработчиков

---

#### 2.3. Dependency Inversion Principle (DIP)
**Проблема:** Handlers напрямую зависят от конкретных реализаций

**Примеры:**
- Прямые вызовы `get_db()`, `SyncService()`, `CursorCLIService()`
- Нет абстракций для тестирования

**Решение:**
- Использовать dependency injection
- Создать интерфейсы для сервисов

---

### 3. Нарушения принципа KISS

#### 3.1. Сложная логика в обработчиках
**Проблема:** Обработчики содержат слишком много логики

**Примеры:**
- `confirm_query_handler` в `callbacks.py` (строки 31-133) - слишком длинный
- `voice_handler` в `voice.py` (строки 185-369) - слишком сложный

**Решение:** Разбить на более мелкие функции

---

#### 3.2. Избыточная вложенность
**Проблема:** Много уровней вложенности усложняет чтение

**Примеры:**
- Вложенные try-except блоки
- Множественные проверки условий

**Решение:** Использовать early returns, guard clauses

---

### 4. Другие проблемы

#### 4.1. Магические строки
**Проблема:** Хардкод строковых значений

**Примеры:**
- `"query_with_kb"`, `"empty_chat"` - типы сессий
- `"active"`, `"completed"` - статусы сессий
- `"user"`, `"assistant"` - роли сообщений

**Решение:** Создать константы в `utils/constants.py`

---

#### 4.2. Дублирование FakeMessage классов
**Проблема:** Класс `FakeMessage` создается в нескольких местах

**Примеры:**
- `callbacks.py`: строки 366-372, 413-419, 801-807, и др.
- `commands.py`: строки 881-887

**Решение:** Вынести в `utils/telegram_helpers.py`

---

#### 4.3. Непоследовательная обработка ошибок
**Проблема:** Разные подходы к обработке ошибок

**Примеры:**
- Иногда используется `logger.error`, иногда `logger.warning`
- Разные форматы сообщений об ошибках

**Решение:** Стандартизировать обработку ошибок

---

## План рефакторинга

### Этап 1: Создание сервисов (Приоритет: Высокий)

#### 1.1. QueryProcessingService
**Файл:** `services/query_processing_service.py`

**Методы:**
- `process_query(query, session_id, attached_files=None) -> tuple[str, List[Dict]]`
- `handle_file_changes(session_id, changes, message) -> None`
- `send_response(message, response_text, reply_markup=None) -> None`

**Зависимости:**
- `CursorCLIService`
- `SyncService`
- `DatabaseInterface`

**Рефакторинг:**
- Объединить `process_final_query` и `process_text_query_after_transcription`
- Вынести логику обработки изменений файлов
- Вынести логику отправки ответов

---

#### 1.2. SessionService
**Файл:** `services/session_service.py`

**Методы:**
- `get_or_create_active_session(user_id, username, session_type="query_with_kb") -> Dict`
- `ensure_user_and_session(user_id, username) -> tuple[Dict, Dict]`
- `deactivate_current_session(user_id) -> None`
- `create_new_session(user_id, session_type="query_with_kb") -> Dict`

**Зависимости:**
- `DatabaseInterface`

**Рефакторинг:**
- Убрать дублирование создания/получения сессий из всех handlers

---

#### 1.3. ResponseFormatterService
**Файл:** `services/response_formatter_service.py` (или расширить `utils/message_helpers.py`)

**Методы:**
- `send_formatted_message(message, text, reply_markup=None) -> None`
- `format_file_changes_info(changes, sync_success) -> str`

**Рефакторинг:**
- Вынести логику форматирования и отправки ответов

---

### Этап 2: Улучшение утилит (Приоритет: Высокий)

#### 2.1. Расширить `utils/message_helpers.py`
**Добавить:**
- `send_formatted_message()` - универсальная отправка с fallback
- `format_file_changes_info()` - форматирование информации об изменениях

#### 2.2. Создать `utils/session_helpers.py`
**Добавить:**
- `format_sessions_list()` - форматирование списка сессий
- `get_user_sessions_for_display()` - получение сессий для отображения
- `format_session_details()` - форматирование деталей сессии

#### 2.3. Создать `utils/telegram_helpers.py`
**Добавить:**
- `create_fake_message_from_callback()` - создание FakeMessage из CallbackQuery
- `create_fake_message_from_message()` - создание FakeMessage из Message

#### 2.4. Создать `utils/constants.py`
**Добавить:**
- `SessionType` - enum для типов сессий
- `SessionStatus` - enum для статусов сессий
- `MessageRole` - enum для ролей сообщений
- `ChangeType` - enum для типов изменений файлов

---

### Этап 3: Рефакторинг handlers (Приоритет: Средний)

#### 3.1. Рефакторинг `handlers/messages.py`
**Изменения:**
- Использовать `QueryProcessingService.process_query()`
- Использовать `SessionService.get_or_create_active_session()`
- Упростить обработчики, убрать бизнес-логику

#### 3.2. Рефакторинг `handlers/voice.py`
**Изменения:**
- Использовать `QueryProcessingService.process_query()`
- Использовать `SessionService.get_or_create_active_session()`
- Упростить обработчик голосовых сообщений

#### 3.3. Рефакторинг `handlers/callbacks.py`
**Изменения:**
- Использовать `SessionService` для управления сессиями
- Использовать `utils/session_helpers` для форматирования
- Использовать `utils/telegram_helpers` для FakeMessage
- Добавить декоратор `@require_admin` для административных действий
- Разбить длинные обработчики на более мелкие функции

#### 3.4. Рефакторинг `handlers/commands.py`
**Изменения:**
- Использовать `SessionService` для управления сессиями
- Использовать `utils/session_helpers` для форматирования
- Использовать `utils/telegram_helpers` для FakeMessage
- Упростить административные обработчики

---

### Этап 4: Улучшение SyncService (Приоритет: Средний)

#### 4.1. Расширить `services/sync_service.py`
**Добавить:**
- `sync_with_progress(message, show_notification=True) -> bool`
- `_create_progress_callback(message) -> Callable`
- Вынести логику обработки Flood control

**Рефакторинг:**
- Убрать дублирование логики синхронизации из handlers

---

### Этап 5: Middleware и декораторы (Приоритет: Низкий) ✅ ВЫПОЛНЕНО

#### 5.1. Создать `middleware/admin_middleware.py` ✅
**Добавлено:**
- ✅ Декоратор `@require_admin` для проверки прав администратора
- ✅ Поддержка как для `Message`, так и для `CallbackQuery`
- ✅ Автоматическая отправка сообщения об ошибке

#### 5.2. Улучшить `middleware/access_control.py`
**Проверить:**
- Можно ли объединить с AdminMiddleware
- Улучшить обработку ошибок

---

### Этап 6: Тестирование и документация (Приоритет: Средний)

#### 6.1. Написать тесты для новых сервисов
- `test_query_processing_service.py`
- `test_session_service.py`
- `test_response_formatter_service.py`

#### 6.2. Обновить документацию
- Описать новые сервисы
- Обновить архитектурную документацию
- Добавить примеры использования

---

## Порядок выполнения

### Фаза 1: Подготовка (1-2 дня) ✅ ВЫПОЛНЕНО
1. ✅ Создать `utils/constants.py` с константами
   - Создан файл с enum классами: `SessionType`, `SessionStatus`, `MessageRole`, `ChangeType`
2. ✅ Создать `utils/telegram_helpers.py` с FakeMessage
   - Создан класс `FakeMessage` для переиспользования обработчиков команд в callback-обработчиках
3. ✅ Расширить `utils/message_helpers.py`
   - Добавлена функция `send_formatted_message()` для универсальной отправки с fallback (HTML → Markdown V2 → Plain text)
   - Добавлена функция `format_file_changes_info()` для форматирования информации об изменениях файлов

### Фаза 2: Сервисы (3-5 дней) ✅ ВЫПОЛНЕНО
1. ✅ Создать `SessionService`
   - Создан `services/session_service.py` с методами:
     - `get_or_create_active_session()` - получение/создание активной сессии
     - `ensure_user_and_session()` - обеспечение пользователя и сессии
     - `deactivate_current_session()` - деактивация текущей сессии
     - `create_new_session()` - создание новой сессии
2. ✅ Создать `QueryProcessingService`
   - Создан `services/query_processing_service.py` с методами:
     - `process_query()` - обработка запроса через Cursor CLI
     - `handle_file_changes()` - обработка изменений файлов
   - Объединена логика из `process_final_query()` и `process_text_query_after_transcription()`
3. ✅ Расширить `SyncService`
   - Добавлен метод `sync_with_progress()` для синхронизации с отображением прогресса
   - Добавлен метод `_create_progress_callback()` для создания callback с защитой от Flood control
4. ✅ Создать `utils/session_helpers.py`
   - Добавлена функция `get_user_sessions_for_display()` для получения сессий с пагинацией
   - Добавлена функция `format_sessions_list()` для форматирования списка сессий
   - Добавлена функция `format_session_details()` для форматирования деталей сессии

### Фаза 3: Рефакторинг handlers (5-7 дней) ✅ ВЫПОЛНЕНО
1. ✅ Рефакторинг `messages.py`
   - Заменен `process_final_query()` на использование `QueryProcessingService`
   - Заменено дублирование создания сессий на `SessionService`
   - Используется `send_formatted_message()` вместо дублирующегося кода
2. ✅ Рефакторинг `voice.py`
   - Заменен `process_text_query_after_transcription()` на использование `QueryProcessingService`
   - Заменено дублирование создания сессий на `SessionService`
   - Используется `send_formatted_message()` вместо дублирующегося кода
3. ✅ Рефакторинг `callbacks.py`
   - Заменено дублирование создания сессий на `SessionService`
   - Используется `utils/session_helpers` для форматирования списков сессий
   - Используется `utils/telegram_helpers` для `FakeMessage`
   - Заменен `process_final_query()` на `QueryProcessingService`
4. ✅ Рефакторинг `commands.py`
   - Заменено дублирование создания сессий на `SessionService`
   - Используется `utils/session_helpers` для форматирования списков сессий
   - Используется `utils/telegram_helpers` для `FakeMessage`
   - Используется `sync_with_progress()` для синхронизации

### Фаза 4: Улучшения (2-3 дня) 🔄 В ПРОЦЕССЕ
1. ✅ Создать AdminMiddleware/декоратор
   - Создан декоратор `@require_admin` в `middleware/admin_middleware.py`
   - Применен ко всем административным обработчикам в `callbacks.py` и `commands.py`
   - Устранено 11+ дублирований проверки прав администратора
2. ⏳ Стандартизировать обработку ошибок
3. ⏳ Оптимизировать импорты

### Фаза 5: Тестирование (2-3 дня) ⏳ ОЖИДАЕТ
1. ⏳ Написать тесты
2. ⏳ Провести ручное тестирование
3. ⏳ Исправить найденные баги

---

## Метрики успеха

### Код
- [ ] Уменьшение дублирования кода на 60%+
- [ ] Уменьшение размера handlers на 40%+
- [ ] Улучшение покрытия тестами до 70%+

### Качество
- [ ] Все handlers < 100 строк
- [ ] Все методы < 50 строк
- [ ] Цикломатическая сложность < 10

### Производительность
- [ ] Нет регрессий в производительности
- [ ] Улучшение читаемости кода (субъективно)

---

## Риски и митигация

### Риск 1: Регрессии при рефакторинге
**Митигация:**
- Поэтапный рефакторинг
- Тестирование после каждого этапа
- Сохранение обратной совместимости API

### Риск 2: Увеличение сложности из-за новых абстракций
**Митигация:**
- Следовать принципу KISS
- Документировать новые сервисы
- Использовать понятные имена

### Риск 3: Время на рефакторинг
**Митигация:**
- Приоритизировать критичные изменения
- Можно делать постепенно, не все сразу

---

## Примечания

- Рефакторинг можно делать постепенно, не обязательно все сразу
- Начать с самых критичных дублирований (QueryProcessingService, SessionService)
- После каждого этапа тестировать и коммитить
- Можно использовать feature flags для постепенного внедрения

