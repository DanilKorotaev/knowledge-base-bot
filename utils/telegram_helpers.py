"""
Утилиты для работы с Telegram API
"""
from typing import Optional
from aiogram.types import CallbackQuery, Message


class FakeMessage:
    """
    Вспомогательный класс для создания объекта Message из CallbackQuery
    Используется для переиспользования обработчиков команд в callback-обработчиках
    """
    
    def __init__(self, callback: CallbackQuery):
        """
        Создать FakeMessage из CallbackQuery
        
        Args:
            callback: CallbackQuery объект
        """
        self.from_user = callback.from_user
        self.answer = callback.message.answer
        self.text = None
        self.message_id = callback.message.message_id
        self.chat = callback.message.chat
    
    @classmethod
    def from_message(cls, message: Message) -> 'FakeMessage':
        """
        Создать FakeMessage из Message (для совместимости)
        
        Args:
            message: Message объект
        
        Returns:
            FakeMessage: Новый экземпляр FakeMessage
        """
        fake = cls.__new__(cls)
        fake.from_user = message.from_user
        fake.answer = message.answer
        fake.text = message.text
        fake.message_id = message.message_id
        fake.chat = message.chat
        return fake

