"""
Утилиты для работы с сессиями
"""
import html
from typing import List, Dict, Any, Optional, Tuple
from utils.db_helpers import get_db
from utils.constants import MessageRole


async def get_user_sessions_for_display(
    user_id: int,
    page: int = 0,
    per_page: int = 8,
) -> Tuple[List[Dict[str, Any]], Optional[int], int]:
    """Сессии страницы, от новых сообщений к старым. Архив и удалённые не входят."""
    db = await get_db()

    total_count = await db.count_user_sessions(user_id, exclude_deleted=True)
    start_idx = page * per_page
    page_sessions = await db.get_user_sessions_with_counts(
        user_id,
        limit=per_page,
        offset=start_idx,
        exclude_deleted=True,
    )

    for session in page_sessions:
        session["messages_count"] = int(session.get("message_count") or 0)

    active_session = await db.get_active_session(user_id)
    active_session_id = active_session["id"] if active_session else None

    return page_sessions, active_session_id, total_count


def session_title(session: Dict[str, Any]) -> str:
    """Человеческое имя сессии. Числовой id остаётся только в callback-данных."""
    title = " ".join(str(session.get("display_title") or "").split())
    return title or "Без названия"


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
    
    response = "📋 <b>Ваши сессии</b>\n"
    response += "Сверху те, где последнее сообщение новее.\n\n"
    
    for session in sessions:
        title = html.escape(session_title(session))
        marker = " · в этом чате" if session["id"] == active_session_id else ""
        response += f"<b>{title}</b>{marker}\n"
    
    total = total_count if total_count is not None else len(sessions)
    if total > per_page:
        pages = (total + per_page - 1) // per_page
        response += f"\n<i>Страница {page + 1} из {pages}. Всего {total}.</i>"
    
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
    messages = await db.get_session_messages(session_id, limit=10)
    
    response = f"📋 <b>{html.escape(session_title(session))}</b>\n"
    if is_active:
        response += "Сейчас открыта в этом чате.\n"
    response += f"\nСообщений: {len(messages)}\n\n"
    
    if messages:
        response += "<b>Последние сообщения:</b>\n\n"
        for msg in messages[-5:]:  # Показать последние 5 сообщений
            role_emoji = "👤" if msg["role"] == str(MessageRole.USER) else "🤖"
            text_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            response += f"{role_emoji} {text_preview}\n"
    
    return response

