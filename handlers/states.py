"""
FSM состояния для бота
"""
from aiogram.fsm.state import State, StatesGroup


class QueryStates(StatesGroup):
    """Состояния для работы с запросами"""
    waiting_for_query = State()
    processing_query = State()
    waiting_for_confirmation = State()
    collecting_messages = State()  # Режим сбора сообщений перед отправкой


class AdminStates(StatesGroup):
    """Состояния для административных команд"""
    waiting_for_user_selection = State()  # Ожидание выбора пользователя из списка
    waiting_for_user_contact = State()  # Ожидание контакта или ID пользователя

