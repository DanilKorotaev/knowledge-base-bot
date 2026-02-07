# Задача: Гибридный подход — использование встроенных сессий Cursor CLI

## Статус: pending

## Описание

Перейти на использование встроенных сессий Cursor CLI (`--resume`) вместо ручной передачи истории сообщений в промпте. Это позволит:
- Экономить токены (не дублировать историю в каждом запросе)
- Cursor CLI сам помнит контекст: прочитанные файлы, изменения, весь диалог
- Убрать ограничение на 10 сообщений / 500 символов в контексте
- Повысить качество ответов (AI видит полный контекст, а не обрезанный)

## Результаты исследования

### Подтверждённые возможности Cursor CLI

```bash
# Создать пустой чат → возвращает UUID
cursor-agent create-chat
# → 441adc68-5043-4fd2-98e6-500b98f7fcff

# Первый запрос в чат
cursor-agent -p --resume <chatId> --force "Привет"
# → Привет! Чем могу помочь?

# Продолжение диалога (помнит предыдущие сообщения)
cursor-agent -p --resume <chatId> --force "Что я написал?"
# → Вы написали: «Привет»

# При невалидном chatId → exit code 1, ошибка
cursor-agent -p --resume "невалидный-ид" --force "тест"
# → exit code 1, "Error"

# Продолжить последний чат (без указания ID)
cursor-agent --continue
```

### Хранение чатов

- Путь: `/root/.cursor/chats/<workspace-hash>/<chatId>/store.db`
- Формат: SQLite база
- **Проблема**: данные хранятся в файловой системе Docker-контейнера, при `docker compose build` теряются

## План реализации

### 1. Персистентность чатов Cursor CLI (Docker)

**Файл:** `docker-compose.yml`

Добавить volume для хранения чатов Cursor CLI:
```yaml
volumes:
  - ~/.local/share/knowledge-base-bot/kb:/var/knowledge-base-bot/kb
  - ./logs:/app/logs
  - cursor_chats:/root/.cursor/chats  # NEW: персистентность чатов Cursor CLI
```

Это необходимо, чтобы чаты не терялись при пересборке/рестарте контейнера.

### 2. Новое поле в БД: `cursor_chat_id`

**Файлы:** `database/base.py`, `database/sqlite_db.py`, `database/postgresql_db.py`

Добавить поле `cursor_chat_id TEXT` в таблицу `sessions`:
```sql
ALTER TABLE sessions ADD COLUMN cursor_chat_id TEXT;
```

- Заполняется при первом запросе в сессии (через `cursor-agent create-chat`)
- Используется при последующих запросах (через `--resume`)

### 3. Изменение CursorCLIService

**Файл:** `services/cursor_cli_service.py`

#### 3.1 Новый метод: `create_chat()`
```python
async def create_chat(self) -> Optional[str]:
    """Создать новый чат в Cursor CLI, вернуть chatId (UUID)"""
    process = await asyncio.create_subprocess_exec(
        "cursor-agent", "create-chat",
        cwd=str(self.kb_path),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        return stdout.decode().strip()
    return None
```

#### 3.2 Изменение метода `process_query()`

Добавить параметр `cursor_chat_id: Optional[str]`:
- Если `cursor_chat_id` передан → использовать `--resume <cursor_chat_id>` вместо передачи истории
- Если `--resume` вернул ошибку (exit code 1) → fallback на ручную передачу истории
- Убрать передачу `session_messages` в промпт, когда используется `--resume`

Логика:
```python
if cursor_chat_id:
    cmd = ["cursor-agent", "-p", "--resume", cursor_chat_id, "--force"]
    # НЕ добавляем историю в промпт — Cursor CLI помнит сам
    full_query = query  # только текущий запрос
else:
    cmd = ["cursor-agent", "-p", "--force"]
    # Старое поведение: передаём историю в промпте
    full_query = self._build_query_with_context(query, session_messages)
```

#### 3.3 Метод `_build_query_with_context()` — оставить как fallback

Не удалять — используется как запасной вариант, когда `--resume` недоступен.

### 4. Изменение QueryProcessingService

**Файл:** `services/query_processing_service.py`

В методе `process_query()`:
1. Получить `cursor_chat_id` из сессии в БД
2. Если `cursor_chat_id` пуст (первый запрос) → вызвать `create_chat()`, сохранить ID в БД
3. Передать `cursor_chat_id` в `cursor_service.process_query()`
4. Если `--resume` не сработал → обнулить `cursor_chat_id` в БД, повторить с fallback

### 5. Изменение SessionService

**Файл:** `services/session_service.py`

При создании новой сессии (`create_new_session`):
- Пока НЕ создавать `cursor_chat_id` — он создастся лениво при первом запросе
- Это позволяет не тратить ресурсы на `create-chat` если пользователь создал сессию, но не отправил запрос

### 6. Обновление документации

**Файл:** `docs/CURSOR_CLI_PERFORMANCE.md`

Обновить раздел про сессии — текущее описание уже содержит информацию о `--resume`, но нужно пометить как "реализовано".

## Порядок реализации

1. **docker-compose.yml** — добавить volume для чатов ← первым делом
2. **Миграция БД** — добавить поле `cursor_chat_id`
3. **CursorCLIService** — добавить `create_chat()`, изменить `process_query()`
4. **QueryProcessingService** — интегрировать логику с `cursor_chat_id`
5. **Тестирование** — проверить сценарии:
   - Новая сессия → первый запрос → создаётся chat → ответ
   - Продолжение диалога → `--resume` → помнит контекст
   - Невалидный chatId (после пересборки без volume) → fallback на историю
   - Переключение между сессиями → разные chatId
6. **Документация** — обновить

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Чаты теряются при пересборке Docker | Средняя | Volume + fallback на ручную историю |
| `--resume` иногда не работает | Низкая | Fallback с retry |
| Cursor CLI обновился и сломал API | Низкая | Fallback на старый подход |
| Накопление старых чатов в volume | Средняя | Периодическая очистка (cron/при старте бота) |

## Оценка

- Сложность: средняя
- Время: ~3-4 часа
- Влияние: значительное улучшение качества диалогов и экономия токенов

