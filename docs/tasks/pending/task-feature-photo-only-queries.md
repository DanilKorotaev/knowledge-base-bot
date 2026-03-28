# Поддержка фото/файлов как самостоятельных запросов (без текста)

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции / Исправление legacy

## Описание

Сейчас при отправке фото или документа вне режима сбора сообщений бот отвечает заглушкой с упоминанием устаревшей команды `/collect`. Нужно:

1. Убрать legacy-заглушку и ссылку на `/collect`
2. Реализовать обработку фото/документов как полноценных запросов к базе знаний (аналогично текстовым сообщениям)

## Проблема

В `handlers/media.py` для фото и документов вне режима сбора (`collecting_messages`) используется заглушка:

```python
# Строки 106-111 (photo_handler)
await message.answer(
    "📷 Получено фото.\n\n"
    "Обработка фото будет реализована позже.\n"
    "Используйте /collect для включения режима сбора сообщений."
)

# Строки 201-206 (document_handler)
await message.answer(
    f"📄 Получен документ: {document.file_name}\n\n"
    "Обработка документов будет реализована позже.\n"
    "Используйте /collect для включения режима сбора сообщений."
)
```

Проблемы:
- Команда `/collect` не поддерживается (legacy)
- Фото/документ без текста не обрабатывается вообще
- Пользователь не может просто скинуть скриншот заправки и получить результат

## Цели

1. Удалить legacy-заглушки с упоминанием `/collect`
2. Реализовать обработку фото/документов как самостоятельных запросов к Cursor CLI
3. Фото/документ должен скачиваться, сохраняться в `attachments/` и передаваться как прикрепленный файл в `QueryProcessingService.process_query()`
4. Если к фото есть подпись (caption) — использовать её как текст запроса
5. Если подписи нет — сформировать автоматический запрос, описывающий, что пользователь отправил файл

## Задачи

### Удаление legacy

- [ ] Убрать заглушку в `photo_handler` (строки 106-111) — заменить на реальную обработку
- [ ] Убрать заглушку в `document_handler` (строки 201-206) — заменить на реальную обработку
- [ ] Убрать любые упоминания `/collect` в сообщениях бота (если есть в других местах)

### Реализация обработки фото в обычном режиме

- [ ] В `photo_handler` для обычного режима (не `collecting_messages`):
  - Скачать фото через `download_telegram_file`
  - Сохранить в `attachments/photos/`
  - Получить или создать активную сессию (`SessionService.get_or_create_active_session`)
  - Сформировать текст запроса:
    - Если есть `message.caption` → использовать его
    - Если нет → использовать автоматический текст: `"Пользователь отправил фото без подписи. Проанализируй содержимое фото и выполни соответствующее действие."`
  - Вызвать `QueryProcessingService.process_query()` с `attached_files=[photo_path]`

### Реализация обработки документов в обычном режиме

- [ ] В `document_handler` для обычного режима:
  - Аналогично фото, но сохранение в `attachments/documents/`
  - Текст запроса: caption или автоматический с именем файла

### Тестирование

- [ ] Проверить отправку фото без подписи → бот должен обработать
- [ ] Проверить отправку фото с подписью → подпись используется как запрос
- [ ] Проверить отправку документа без подписи
- [ ] Проверить отправку документа с подписью
- [ ] Проверить, что режим сбора сообщений (`collecting_messages`) продолжает работать как раньше

## Пример реализации

```python
# В photo_handler, замена заглушки (строки 106-111):

# Обычный режим — обработать как запрос к базе знаний
logger.info(f"Получено фото в обычном режиме от пользователя {user_id}")
processing_message = await message.answer("📷 Обрабатываю фото...")

try:
    # Скачать и сохранить фото
    photo_path = await download_telegram_file(message.bot, photo.file_id)
    if not photo_path:
        await processing_message.edit_text("❌ Не удалось скачать фото.")
        return

    kb_path = config.LOCAL_KB_PATH
    attachments_dir = kb_path / "attachments" / "photos"
    attachments_dir.mkdir(parents=True, exist_ok=True)
    final_path = attachments_dir / f"{photo.file_id}.jpg"
    shutil.move(str(photo_path), str(final_path))

    # Сформировать запрос
    query = message.caption or (
        "Пользователь отправил фото без подписи. "
        "Проанализируй содержимое фото и выполни соответствующее действие."
    )

    # Получить или создать сессию
    session_service = SessionService()
    active_session = await session_service.get_or_create_active_session(
        user_id=user_id,
        username=message.from_user.username,
        session_type=SessionType.QUERY_WITH_KB
    )

    # Обработать запрос
    await processing_message.delete()
    query_service = QueryProcessingService()
    await query_service.process_query(
        query=query,
        session_id=active_session["id"],
        message=message,
        attached_files=[final_path]
    )
except Exception as e:
    logger.error(f"Ошибка при обработке фото: {e}", exc_info=True)
    await processing_message.edit_text(f"❌ Ошибка: {str(e)}")
```

## Связанные файлы

- `handlers/media.py` — основной файл для изменений
- `services/query_processing_service.py` — сервис обработки запросов
- `services/session_service.py` — управление сессиями
- `utils/file_helpers.py` — скачивание файлов из Telegram
- `agent/system_prompt.md` — системный промпт (может потребоваться обновление)

## Зависимости

- Для полноценной работы с фото-only запросами (например, распознавание скриншотов заправки) также необходимо обновить системный промпт базы знаний — см. связанную задачу в `Документация/Задачи/`
