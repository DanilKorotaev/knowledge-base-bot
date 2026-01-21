"""
Клавиатуры для бота
"""
from typing import List, Dict, Optional
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton,
    KeyboardButtonRequestUsers
)


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


def get_main_menu_inline_keyboard_with_admin(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню как inline-кнопки с опциональной кнопкой админки"""
    keyboard = [
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
    
    if is_admin:
        keyboard.append([
            InlineKeyboardButton(text="⚙️ Админка", callback_data="admin_menu")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню администратора"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_list_users")
            ],
            [
                InlineKeyboardButton(text="✅ Разрешить доступ", callback_data="admin_allow_start"),
                InlineKeyboardButton(text="❌ Запретить доступ", callback_data="admin_disallow_start")
            ],
            [
                InlineKeyboardButton(text="👑 Назначить админа", callback_data="admin_set_admin_start"),
                InlineKeyboardButton(text="🔻 Убрать админа", callback_data="admin_remove_admin_start")
            ],
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
            ]
        ]
    )
    return keyboard


def get_users_selection_keyboard(
    users: List[Dict],
    action: str,  # "allow", "disallow", "set_admin", "remove_admin"
    page: int = 0,
    per_page: int = 10
) -> InlineKeyboardMarkup:
    """Клавиатура для выбора пользователя из списка с пагинацией"""
    keyboard = []
    
    # Показать пользователей для текущей страницы
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    # Каждый пользователь - одна кнопка
    for user in page_users:
        telegram_id = user["telegram_id"]
        username = user.get("username") or "без username"
        admin_marker = "👑" if user.get("is_admin") else ""
        allowed_marker = "✅" if user.get("is_allowed") else "❌"
        
        # Обрезаем username если слишком длинный
        display_username = username[:20] if len(username) > 20 else username
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{admin_marker} {allowed_marker} {telegram_id} (@{display_username})",
                callback_data=f"admin_select_user_{action}_{telegram_id}"
            )
        ])
    
    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_users_page_{action}_{page - 1}")
        )
    if end_idx < len(users):
        nav_buttons.append(
            InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admin_users_page_{action}_{page + 1}")
        )
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Кнопка отмены
    keyboard.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_contact_request_keyboard(action: str) -> tuple[ReplyKeyboardMarkup, InlineKeyboardMarkup]:
    """
    Клавиатура с просьбой отправить контакт или ID.
    Возвращает tuple: (reply_keyboard с кнопкой выбора пользователя, inline_keyboard)
    """
    # Reply-клавиатура с кнопкой выбора пользователя через UI Telegram
    reply_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="👤 Выбрать пользователя",
                    request_users=KeyboardButtonRequestUsers(
                        request_id=hash(action) % 1000000,  # Уникальный ID для идентификации запроса
                        user_is_bot=False,  # Только реальные пользователи
                        user_is_premium=None  # Любые пользователи
                    )
                )
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    # Inline-клавиатура с альтернативными опциями
    inline_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Выбрать из списка", callback_data=f"admin_list_for_{action}")
            ],
            [
                InlineKeyboardButton(text="📝 Ввести ID вручную", callback_data=f"admin_manual_id_{action}")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_menu")
            ]
        ]
    )
    
    return reply_keyboard, inline_keyboard

