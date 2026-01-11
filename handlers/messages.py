"""
Обработчики текстовых сообщений
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def text_message_handler(message: Message, state: FSMContext):
    """Обработчик текстовых сообщений"""
    # TODO: Реализовать обработку текстовых сообщений
    # 1. Получить активную сессию пользователя
    # 2. Добавить сообщение пользователя в историю сессии
    # 3. Если сессия с контекстом базы знаний:
    #    - Вызвать Cursor CLI через cursor_cli_service.process_query()
    # 4. Получить ответ от Cursor CLI и список изменений файлов
    # 5. Отследить изменения в БД
    # 6. Отправить ответ пользователю
    # 7. Сохранить оба сообщения в БД
    # 8. Синхронизировать изменения с NextCloud (если были изменения)
    
    await message.answer(
        f"📝 Получено сообщение: {message.text}\n\n"
        "Обработка текстовых сообщений будет реализована позже."
    )

