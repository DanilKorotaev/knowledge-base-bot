"""
Утилиты для работы с сессиями
"""
from typing import List, Dict, Any, Optional, Tuple
from utils.db_helpers import get_db
from utils.constants import SessionType, SessionStatus, MessageRole


async def get_user_sessions_for_display(
    user_id: int,
    page: int = 0,
    per_page: int = 5,
    limit: int = 20
) -> Tuple[List[Dict[str, Any]], Optional[int], int]:
    """
    Получить сессии пользователя для отображения с пагинацией
    
    Args:
        user_id: ID пользователя в БД
        page: Номер страницы (начиная с 0)
        per_page: Количество сессий на странице
        limit: Максимальное количество сессий для получения из БД
    
    Returns:
        Tuple[List[Dict], Optional[int], int]: (сессии для страницы, ID активной сессии, общее количество сессий)
    """
    db = await get_db()

    total_count = await db.count_user_sessions(user_id, exclude_deleted=True)
    # Keep historical cap used by Telegram UI (limit), then paginate within it.
    capped_total = min(total_count, limit)
    start_idx = page * per_page
    page_sessions = await db.get_user_sessions_with_counts(
        user_id,
        limit=per_page,
        offset=start_idx,
        exclude_deleted=True,
    )
    # If caller asked for a historical window smaller than DB total, trim last page.
    if start_idx + len(page_sessions) > capped_total:
        page_sessions = page_sessions[: max(0, capped_total - start_idx)]

    for session in page_sessions:
        session["messages_count"] = int(session.get("message_count") or 0)

    active_session = await db.get_active_session(user_id)
    active_session_id = active_session["id"] if active_session else None

    return page_sessions, active_session_id, capped_total



def format_sessions_list(
    sessions: List[Dict[str, Any]],
    active_session_id: Optional[int],
    page: int = 0,
    per_page: int = 5,
    total_count: Optional[int] = None
) -> str:
    """
    Форматировать список сессий для отображения
    
    Args:
        sessions: Список сессий для текущей страницы
        active_session_id: ID активной сессии (если есть)
        page: Номер страницы
        per_page: Количество сессий на странице
        total_count: Общее количество сессий (если None, используется len(sessions))
    
    Returns:
        str: Отформатированный текст со списком сессий
    """
    if not sessions:
        return "ℹ️ У вас нет сессий.\n\nИспользуйте кнопку '📚 Новый запрос' для создания новой сессии."
    
    response = "📋 <b>Ваши сессии:</b>\n\n"
    response += "Нажмите на сессию, чтобы увидеть детали и действия.\n\n"
    
    for session in sessions:
        session_type_emoji = "📚" if session["session_type"] == str(SessionType.QUERY_WITH_KB) else "💬"
        status_emoji = "🟢" if session["id"] == active_session_id else "⚪"
        session_type_label = "С контекстом БЗ" if session["session_type"] == str(SessionType.QUERY_WITH_KB) else "Без контекста"
        
        messages_count = session.get("messages_count", 0)
        
        response += f"{session_type_emoji} <b>#{session['id']}</b> {status_emoji}\n"
        response += f"  {session_type_label} • {messages_count} сообщений\n\n"
    
    # Добавить информацию о пагинации
    total = total_count if total_count is not None else len(sessions)
    if total > per_page:
        shown_count = len(sessions)
        response += f"\n<i>Страница {page + 1}. Показано {shown_count} из {total} сессий.</i>"
    
    return response


async def format_session_details(session: Dict[str, Any], is_active: bool = False) -> str:
    """
    Форматировать детали сессии для отображения
    
    Args:
        session: Информация о сессии
        is_active: Является ли сессия активной
    
    Returns:
        str: Отформатированный текст с деталями сессии
    """
    from utils.db_helpers import get_db
    
    db = await get_db()
    
    session_id = session["id"]
    session_type_label = "С контекстом БЗ" if session["session_type"] == str(SessionType.QUERY_WITH_KB) else "Без контекста"
    status_label = "🟢 Активна" if is_active else f"⚪ {session['status']}"
    
    # Получить сообщения сессии
    messages = await db.get_session_messages(session_id, limit=10)
    
    response = f"📋 <b>Сессия #{session_id}</b>\n\n"
    response += f"Статус: {status_label}\n"
    response += f"Тип: {session_type_label}\n"
    response += f"Сообщений: {len(messages)}\n\n"
    
    if messages:
        response += "<b>Последние сообщения:</b>\n\n"
        for msg in messages[-5:]:  # Показать последние 5 сообщений
            role_emoji = "👤" if msg["role"] == str(MessageRole.USER) else "🤖"
            text_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            response += f"{role_emoji} {text_preview}\n"
    
    return response

