"""
Клавиатуры для бота
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Главная клавиатура"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Новый запрос"), KeyboardButton(text="💬 Новый чат")],
            [KeyboardButton(text="📜 История"), KeyboardButton(text="🔄 Синхронизация")],
            [KeyboardButton(text="❓ Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_revert_keyboard(change_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отката изменения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Откатить", callback_data=f"revert_{change_id}")]
        ]
    )
    return keyboard


def get_confirm_query_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения отправки запроса"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить запрос", callback_data="confirm_query"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_query")
            ]
        ]
    )
    return keyboard

