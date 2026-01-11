# Обработка файлов и фото

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация обработки фото и файлов от пользователей с сохранением в базу знаний и синхронизацией с NextCloud.

## Цели

1. Реализовать обработку фото (с подписями и без)
2. Реализовать обработку документов (PDF, DOCX, TXT и т.д.)
3. Реализовать сохранение файлов в локальную копию базы знаний
4. Реализовать синхронизацию файлов с NextCloud
5. Реализовать привязку файлов к сессии запроса
6. Реализовать OCR для фото (опционально, через Vision API)

## Задачи

- [ ] Реализовать получение файла из Telegram
- [ ] Реализовать скачивание файла во временную директорию
- [ ] Реализовать определение типа файла
- [ ] Реализовать сохранение файла в локальную копию базы знаний (в соответствующую папку)
- [ ] Реализовать привязку файла к активной сессии
- [ ] Реализовать синхронизацию файла с NextCloud
- [ ] Реализовать уведомление пользователя о сохранении
- [ ] Реализовать обработку фото с подписями
- [ ] Реализовать OCR для фото (опционально, через Vision API)
- [ ] Реализовать обработку документов (PDF, DOCX, TXT и т.д.)
- [ ] Реализовать обработку больших файлов (проверка размера, прогресс)
- [ ] Реализовать валидацию типов файлов (разрешенные форматы)
- [ ] Реализовать очистку временных файлов после обработки
- [ ] Реализовать обработку ошибок при скачивании/сохранении

## Логика обработки

1. Получить файл из Telegram
2. Скачать файл во временную директорию
3. Определить тип файла
4. Если фото - можно использовать Vision API для извлечения текста
5. Сохранить файл в локальную копию базы знаний (в соответствующую папку)
6. Привязать к активной сессии
7. Синхронизировать с NextCloud
8. Уведомить пользователя о сохранении

## Структура сохранения

```
/var/knowledge-base-bot/kb/
  └── Telegram Attachments/
      └── 2025/
          └── 01/
              └── [session_id]/
                  ├── photo_001.jpg
                  └── document_001.pdf
```

## Технические детали

### Пример реализации

```python
# В handlers/media.py
from services.nextcloud_service import NextCloudService
from utils.file_helpers import save_file_to_kb

@dp.message(F.photo)
async def photo_handler(message: Message, state: FSMContext):
    """Обработка фото"""
    # Получить фото
    photo = message.photo[-1]  # Берем самое большое фото
    
    # Скачать файл
    file = await bot.get_file(photo.file_id)
    temp_path = f"/tmp/{file.file_id}.jpg"
    await bot.download_file(file.file_path, temp_path)
    
    # Сохранить в локальную копию БЗ
    session = await db.get_active_session(message.from_user.id)
    kb_path = save_file_to_kb(
        file_path=temp_path,
        session_id=session["id"] if session else None,
        file_type="photo"
    )
    
    # Синхронизировать с NextCloud
    if config.ENABLE_SYNC:
        nc_service = NextCloudService()
        await nc_service.upload_file(
            local_path=kb_path,
            remote_path=f"{config.NEXTCLOUD_KNOWLEDGE_BASE_PATH}/Telegram Attachments/..."
        )
    
    # Привязать к сессии
    if session:
        await db.add_attachment(
            session_id=session["id"],
            file_type="photo",
            file_id=photo.file_id,
            file_path=kb_path,
            file_name=f"{file.file_id}.jpg",
            file_size=photo.file_size
        )
    
    # Уведомить пользователя
    await message.answer("✅ Фото сохранено в базу знаний")
```

## Связанные файлы

- `handlers/media.py` - обработчики фото и файлов
- `services/nextcloud_service.py` - синхронизация с NextCloud
- `utils/file_helpers.py` - помощники для работы с файлами

