"""
Клавиатуры для бота
"""
from typing import List, Dict, Optional
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Минимальная клавиатура - только главное меню и контекстные кнопки"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_main_menu_inline_keyboard() -> InlineKeyboardMarkup:
    """Главное меню как inline-кнопки"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📚 Новый запрос", callback_data="main_new_query"),
                InlineKeyboardButton(text="💬 Новый чат", callback_data="main_new_chat")
            ],
            [
                InlineKeyboardButton(text="📋 Мои сессии", callback_data="main_sessions"),
                InlineKeyboardButton(text="📜 История", callback_data="main_history")
            ],
            [
                InlineKeyboardButton(text="🔄 Синхронизация", callback_data="main_sync"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="main_help")
            ]
        ]
    )
    return keyboard


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены для FSM-состояний"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_sessions_keyboard(sessions: List[Dict], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура для списка сессий с пагинацией - при клике на сессию показываются детали"""
    keyboard = []
    
    # Показать сессии для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_sessions = sessions[start_idx:end_idx]
    
    # Каждая сессия - одна кнопка, при клике показываются детали
    for session in page_sessions:
        session_id = session["id"]
        session_type_label = "📚" if session["session_type"] == "query_with_kb" else "💬"
        status_emoji = "🟢" if session["status"] == "active" else "⚪"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{session_type_label} #{session_id} {status_emoji}",
                callback_data=f"session_details_{session_id}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"sessions_page_{page - 1}")
        )
    if end_idx < len(sessions):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"sessions_page_{page + 1}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка возврата в главное меню
    keyboard.append([
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_session_details_keyboard(session_id: int, is_active: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура с действиями для конкретной сессии"""
    keyboard = []
    
    # Кнопка переключения (если сессия не активна)
    if not is_active:
        keyboard.append([
            InlineKeyboardButton(
                text="🔄 Переключиться на эту сессию",
                callback_data=f"switch_session_{session_id}"
            )
        ])
    
    # Остальные действия
    keyboard.append([
        InlineKeyboardButton(
            text="👁 Подробнее",
            callback_data=f"view_session_{session_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"delete_session_{session_id}"
        )
    ])
    
    if is_active:
        keyboard.append([
            InlineKeyboardButton(
                text="⏹ Завершить сессию",
                callback_data=f"end_session_{session_id}"
            )
        ])
    
    # Кнопка назад к списку сессий
    keyboard.append([
        InlineKeyboardButton(text="◀️ Назад к списку", callback_data="main_sessions")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_history_keyboard(
    changes: List[Dict],
    session_id: int,
    page: int = 0,
    per_page: int = 5
) -> InlineKeyboardMarkup:
    """Клавиатура для истории изменений с пагинацией"""
    keyboard = []
    
    # Показать изменения для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_changes = changes[start_idx:end_idx]
    
    for change in page_changes:
        change_id = change["id"]
        change_type_emoji = {
            "created": "➕",
            "modified": "✏️",
            "deleted": "🗑"
        }.get(change["change_type"], "📄")
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{change_type_emoji} Откатить",
                callback_data=f"revert_{change_id}"
            ),
            InlineKeyboardButton(
                text="👁 Детали",
                callback_data=f"view_change_{change_id}"
            )
        ])
    
    # Кнопка отката всех изменений сессии
    if changes:
        keyboard.append([
            InlineKeyboardButton(
                text="↩️ Откатить все изменения сессии",
                callback_data=f"revert_session_{session_id}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"history_page_{page - 1}_{session_id}")
        )
    if end_idx < len(changes):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"history_page_{page + 1}_{session_id}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка возврата
    keyboard.append([
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_revert_keyboard(change_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для отката конкретного изменения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="↩️ Откатить", callback_data=f"revert_{change_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_revert")
            ]
        ]
    )
    return keyboard


def get_revert_session_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения отката всех изменений сессии"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить откат",
                    callback_data=f"confirm_revert_session_{session_id}"
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_revert")
            ]
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


def get_delete_session_keyboard(session_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для подтверждения удаления сессии"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Удалить",
                    callback_data=f"confirm_delete_session_{session_id}"
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")
            ]
        ]
    )
    return keyboard


def get_new_query_keyboard() -> tuple[ReplyKeyboardMarkup, InlineKeyboardMarkup]:
    """
    Клавиатура для нового запроса.
    Возвращает tuple: (reply_keyboard, inline_keyboard)
    Reply - только кнопка "Главное меню"
    Inline - кнопка "Режим сбора сообщений"
    """
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Режим сбора сообщений",
                    callback_data="start_collect_mode"
                )
            ]
        ]
    )
    
    return reply_keyboard, inline_keyboard


def get_active_session_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для активной сессии - только контекстные кнопки"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Режим сбора"), KeyboardButton(text="❌ Отмена")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_collecting_messages_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для режима сбора сообщений"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Завершить сбор"), KeyboardButton(text="❌ Отмена")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_collect_mode_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline-кнопка для режима сбора сообщений (показывается при активной сессии)"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Режим сбора сообщений",
                    callback_data="start_collect_mode"
                )
            ]
        ]
    )
    return keyboard


def get_transcribe_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline-кнопка для расшифровки последнего голосового сообщения"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎤 Расшифровать голосовое",
                    callback_data="transcribe_last_voice"
                )
            ]
        ]
    )
    return keyboard

