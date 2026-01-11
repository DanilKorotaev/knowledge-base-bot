# Обработка голосовых сообщений

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация обработки голосовых сообщений с транскрибацией через Whisper API и последующей обработкой как текстовых сообщений.

## Цели

1. Реализовать скачивание голосовых файлов из Telegram
2. Реализовать транскрибацию через Whisper API
3. Реализовать сохранение транскрипции в БД
4. Реализовать обработку транскрипции как текстового сообщения
5. Реализовать команду `/transcribe` для отдельной расшифровки

## Задачи

- [ ] Реализовать скачивание голосового файла из Telegram
- [ ] Реализовать отправку в Whisper API для транскрибации
- [ ] Реализовать сохранение транскрипции в БД
- [ ] Реализовать обработку транскрипции как текстового сообщения
- [ ] Реализовать красивое форматирование расшифровки (как в ChatGPT)
- [ ] Реализовать сохранение языка транскрипции
- [ ] Реализовать команду `/transcribe` для отдельной расшифровки
- [ ] Реализовать обработку больших файлов (разбиение на части)
- [ ] Реализовать поддержку форматов: OGG, MP3, WAV
- [ ] Реализовать получение последнего голосового сообщения для команды `/transcribe`
- [ ] Реализовать обработку ошибок при скачивании/транскрибации
- [ ] Реализовать очистку временных файлов после обработки

## Особенности

- Поддержка форматов: OGG, MP3, WAV
- Обработка больших файлов (разбиение на части)
- Красивое форматирование расшифровки (как в ChatGPT)
- Сохранение языка транскрипции
- Автоматическая обработка транскрипции как текстового сообщения

## Технические детали

### Пример реализации

```python
# В handlers/voice.py
from services.transcription_service import TranscriptionService
from services.openai_service import OpenAIService

@dp.message(F.voice)
async def voice_handler(message: Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    # Скачать файл
    file = await bot.get_file(message.voice.file_id)
    audio_path = f"/tmp/{file.file_id}.ogg"
    await bot.download_file(file.file_path, audio_path)
    
    # Транскрибировать
    openai_service = OpenAIService()
    transcription_service = TranscriptionService(openai_service)
    result = await transcription_service.transcribe(audio_path)
    
    # Сохранить транскрипцию в БД
    session = await db.get_active_session(message.from_user.id)
    if session:
        attachment = await db.add_attachment(
            session_id=session["id"],
            file_type="voice",
            file_id=message.voice.file_id,
            file_name=f"{file.file_id}.ogg",
            file_size=message.voice.file_size
        )
        await db.add_transcription(
            attachment_id=attachment["id"],
            text=result["text"],
            language=result["language"]
        )
    
    # Отправить красивую расшифровку
    await message.answer(
        f"🎤 **Расшифровка:**\n\n{result['text']}",
        parse_mode="Markdown"
    )
    
    # Обработать как текстовое сообщение
    if session:
        await process_text_query(result['text'], message, state)
```

## Связанные файлы

- `handlers/voice.py` - обработчик голосовых сообщений
- `services/transcription_service.py` - сервис транскрибации
- `services/openai_service.py` - работа с OpenAI API (Whisper)
- `handlers/commands.py` - команда `/transcribe`

