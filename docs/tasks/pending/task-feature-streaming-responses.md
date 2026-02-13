# Задача: Стриминг ответов Cursor CLI в Telegram

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Ответ Cursor CLI должен отображаться в Telegram в реальном времени по мере генерации, а не после полного завершения. Обновление сообщения происходит с буферизацией (не посимвольно).

## Проблема

Сейчас `CursorCLIService.process_query()` читает stdout чанками, но **накапливает** весь вывод и возвращает только после завершения процесса. В `QueryProcessingService` ответ отправляется одним блоком. Пользователь видит только "⏳ Обрабатываю запрос..." до самого конца — иногда десятки секунд.

## Решение

Передавать callback `on_chunk` в `process_query()`. При получении каждого чанка — обновлять сообщение в Telegram с буферизацией.

### Архитектура

```
Cursor CLI stdout → чанк → on_chunk callback → StreamingMessageUpdater → edit_text в Telegram
                                                      ↓
                                              буфер + таймер (1.5с)
                                              min 100 символов
                                              Flood control защита
```

## Задачи

### 1. StreamingMessageUpdater

- [ ] Создать класс `StreamingMessageUpdater` в `utils/message_helpers.py`
- [ ] Поля:
  - `message: Message` — исходное сообщение пользователя
  - `typing_message: Message` — сообщение "⏳ Обрабатываю..." (будет обновляться стримом)
  - `buffer: str` — текущий буфер неотправленного текста
  - `full_text: str` — весь накопленный текст
  - `last_update_time: float` — время последнего обновления
  - `update_interval: float = 1.5` — минимальный интервал между обновлениями (секунды)
  - `min_buffer_size: int = 100` — минимальный размер буфера для обновления
  - `first_chunk: bool = True` — первый чанк (обновлять сразу)
- [ ] Метод `async on_chunk(chunk: str)`:
  - Накапливать текст в `buffer` и `full_text`
  - Первый чанк — обновлять сразу (пользователь видит начало ответа)
  - Последующие — обновлять не чаще `update_interval` И не менее `min_buffer_size` символов
- [ ] Метод `async _update_message()`:
  - Добавлять `▌` (курсор) в конце текста — показывает что ответ генерируется
  - Если текст > 4000 символов — показывать хвост с `...` в начале
  - `parse_mode=None` (plain text) — иначе незакрытые теги ломают HTML при стриминге
  - Обработка `"message is not modified"` — игнорировать
  - Обработка `"Flood control"` — увеличить `update_interval` (×2), подождать
  - Другие ошибки — логировать, не прерывать стриминг
- [ ] Метод `async finalize()`:
  - Удалить курсор `▌`
  - Конвертировать полный текст в HTML через `markdown_to_html()`
  - Финально обновить сообщение с `parse_mode=ParseMode.HTML`
  - Если HTML не удалось — fallback на plain text
  - Если текст > 4000 символов — разбить на несколько сообщений (удалить typing_message, отправить новые)
- [ ] Метод `async flush()` — принудительный сброс буфера (вызывается перед finalize)

### 2. Callback в CursorCLIService

- [ ] Добавить параметр `on_chunk: Optional[Callable[[str], Awaitable[None]]] = None` в `process_query()`
- [ ] В цикле чтения stdout (после `stdout_chunks.append(decoded)`, строка ~393) вызывать callback:
  ```python
  if on_chunk and decoded.strip():
      try:
          await on_chunk(decoded)
      except Exception as e:
          logger.debug(f"Ошибка в on_chunk callback: {e}")
  ```

### 3. Интеграция в QueryProcessingService

- [ ] Создавать `StreamingMessageUpdater` в `process_query()`:
  ```python
  typing_message = await message.answer("⏳ Обрабатываю запрос...")
  updater = StreamingMessageUpdater(message, typing_message)
  ```
- [ ] Передавать `updater.on_chunk` в `cursor_service.process_query(on_chunk=updater.on_chunk)`
- [ ] После получения ответа — вызывать `await updater.finalize()`
- [ ] Не удалять `typing_message` отдельно — `finalize()` превращает его в финальное сообщение
- [ ] При ошибке — вызвать `finalize()` или удалить `typing_message` (чтобы не зависало)

### 4. Конфигурация

- [ ] Добавить переменные окружения (опционально):
  - `STREAMING_UPDATE_INTERVAL` — интервал обновления (по умолчанию 1.5с)
  - `STREAMING_MIN_BUFFER` — минимальный размер буфера (по умолчанию 100 символов)
  - `STREAMING_ENABLED` — включить/выключить стриминг (по умолчанию true)

## Ограничения Telegram

| Ограничение | Значение | Как обрабатываем |
|------------|----------|------------------|
| Максимум текста в сообщении | 4096 символов | При стриминге показываем хвост; при finalize — разбиваем |
| Rate limit `edit_message` | ~30 в минуту (на чат) | Буферизация 1.5с |
| Flood control | Динамический, ~20 req/min | Exponential backoff |
| `message is not modified` | Ошибка при повторном тексте | Игнорируем |

## Пример UX

1. Пользователь: "Создай заметку о встрече"
2. Бот: "⏳ Обрабатываю запрос..."
3. Бот (через 3с): "Создаю заметку о встрече в базе знаний...▌"
4. Бот (через 4.5с): "Создаю заметку о встрече в базе знаний.\n\nФайл создан: Документы/Заметки/2026-02-13 Встреча.md\n\nСодержимое:▌"
5. Бот (финально): полный отформатированный ответ с HTML

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| Telegram Flood control при стриминге | Средняя | Буферизация + exponential backoff |
| Cursor CLI не даёт чанки (буферизует вывод) | Средняя | `stdbuf -oL` уже используется + idle timeout |
| HTML-форматирование ломается при стриминге | Средняя | plain text при стриминге, HTML только при finalize |
| Длинный ответ > 4096 символов | Высокая | Хвост при стриминге, split при finalize |
| Callback замедляет чтение stdout | Низкая | try/except + логирование, не блокирует |

## Оценка

- **Сложность**: 🔴 Высокая
- **Время**: ~4-6 часов

## Связанные файлы

- `utils/message_helpers.py` — новый класс `StreamingMessageUpdater`
- `services/cursor_cli_service.py` — параметр `on_chunk` в `process_query()`
- `services/query_processing_service.py` — использование `StreamingMessageUpdater`
- `config.py` — опциональные переменные стриминга

