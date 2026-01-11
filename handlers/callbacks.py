"""
Обработчики callback-запросов (inline-кнопки)
"""
from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

router = Router()


@router.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик callback-запросов"""
    # TODO: Реализовать обработку callback-запросов
    # - Обработка отката изменений
    # - Обработка навигации по истории
    # - Обработка управления сессиями
    
    await callback.answer("Функция будет реализована позже")

