"""
API маршруты для Mini App
"""
import logging
import os
import sys
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

# Добавляем корень проекта в sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .auth import verify_telegram_auth

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


async def _get_db():
    """Получить экземпляр БД"""
    from utils.db_helpers import get_db
    return await get_db()


async def _verify_session_access(session_id: int, telegram_id: int):
    """
    Проверить доступ пользователя к сессии
    
    Returns:
        Tuple[dict, dict]: (session, user)
    
    Raises:
        HTTPException: если сессия не найдена или нет доступа
    """
    db = await _get_db()
    session = await db.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    user = await db.ensure_user(telegram_id)
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этой сессии")
    
    return session, user


@router.get("/sessions")
async def get_sessions(
    status: Optional[str] = Query(None, description="Фильтр по статусу: active, completed, deleted"),
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество сессий"),
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Получить список сессий пользователя"""
    db = await _get_db()
    user = await db.ensure_user(telegram_id)
    
    sessions = await db.get_user_sessions(user["id"], limit=limit, status=status)
    
    # Фильтруем удаленные по умолчанию (если не запрошен конкретный статус)
    if status is None:
        sessions = [s for s in sessions if s.get("status") != "deleted"]
    
    # Получаем активную сессию
    active_session = await db.get_active_session(user["id"])
    active_session_id = active_session["id"] if active_session else None
    
    # Добавляем количество сообщений для каждой сессии
    for session in sessions:
        messages = await db.get_session_messages(session["id"])
        session["messages_count"] = len(messages)
        session["is_active"] = session["id"] == active_session_id
    
    return {
        "sessions": sessions,
        "active_session_id": active_session_id,
        "total": len(sessions)
    }


@router.get("/sessions/search")
async def search_sessions(
    q: str = Query(..., min_length=1, description="Поисковый запрос (ID или текст)"),
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Поиск среди сессий пользователя по ID или содержимому сообщений"""
    db = await _get_db()
    user = await db.ensure_user(telegram_id)
    
    # Получить все сессии пользователя
    all_sessions = await db.get_user_sessions(user["id"], limit=100)
    sessions = [s for s in all_sessions if s.get("status") != "deleted"]
    
    # Получаем активную сессию один раз
    active_session = await db.get_active_session(user["id"])
    active_session_id = active_session["id"] if active_session else None
    
    # Поиск по ID
    try:
        search_id = int(q.strip().lstrip("#"))
        id_matches = [s for s in sessions if s["id"] == search_id]
        if id_matches:
            for s in id_matches:
                messages = await db.get_session_messages(s["id"])
                s["messages_count"] = len(messages)
                s["is_active"] = s["id"] == active_session_id
            return {"sessions": id_matches, "total": len(id_matches)}
    except ValueError:
        pass
    
    # Поиск по содержимому сообщений
    matching_sessions = []
    q_lower = q.lower()
    
    for session in sessions:
        messages = await db.get_session_messages(session["id"])
        session["messages_count"] = len(messages)
        session["is_active"] = session["id"] == active_session_id
        
        # Поиск в сообщениях
        for msg in messages:
            if q_lower in msg["content"].lower():
                matching_sessions.append(session)
                break
    
    return {"sessions": matching_sessions, "total": len(matching_sessions)}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: int,
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Получить детали сессии"""
    session, user = await _verify_session_access(session_id, telegram_id)
    
    db = await _get_db()
    
    # Проверяем, активна ли сессия
    active_session = await db.get_active_session(user["id"])
    session["is_active"] = active_session and active_session["id"] == session_id
    
    # Добавляем количество сообщений
    messages = await db.get_session_messages(session_id)
    session["messages_count"] = len(messages)
    
    return session


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    limit: Optional[int] = Query(None, ge=1, le=500, description="Максимальное количество сообщений"),
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Получить сообщения сессии"""
    session, user = await _verify_session_access(session_id, telegram_id)
    
    db = await _get_db()
    messages = await db.get_session_messages(session_id, limit=limit)
    
    return {
        "messages": messages,
        "session_id": session_id,
        "total": len(messages)
    }


@router.post("/sessions/{session_id}/switch")
async def switch_session(
    session_id: int,
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Переключиться на сессию"""
    session, user = await _verify_session_access(session_id, telegram_id)
    
    db = await _get_db()
    
    # Деактивировать текущую активную сессию
    active_session = await db.get_active_session(user["id"])
    if active_session and active_session["id"] != session_id:
        await db.update_session(active_session["id"], status="completed")
    
    # Активировать выбранную сессию
    await db.update_session(session_id, status="active")
    
    logger.info(f"Пользователь {telegram_id} переключился на сессию #{session_id}")
    
    return {
        "success": True,
        "session_id": session_id,
        "message": f"Переключено на сессию #{session_id}"
    }


@router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: int,
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Завершить сессию"""
    session, user = await _verify_session_access(session_id, telegram_id)
    
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Можно завершить только активную сессию")
    
    db = await _get_db()
    await db.update_session(session_id, status="completed")
    
    logger.info(f"Пользователь {telegram_id} завершил сессию #{session_id}")
    
    return {
        "success": True,
        "session_id": session_id,
        "message": f"Сессия #{session_id} завершена"
    }


@router.post("/sessions/{session_id}/delete")
async def delete_session(
    session_id: int,
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Удалить сессию (пометить как deleted)"""
    session, user = await _verify_session_access(session_id, telegram_id)
    
    db = await _get_db()
    await db.update_session(session_id, status="deleted")
    
    logger.info(f"Пользователь {telegram_id} удалил сессию #{session_id}")
    
    return {
        "success": True,
        "session_id": session_id,
        "message": f"Сессия #{session_id} удалена"
    }


@router.get("/files/view")
async def view_file(
    path: str = Query(..., description="Путь к файлу в базе знаний"),
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Получить содержимое файла из базы знаний"""
    from config import config
    from pathlib import Path
    
    # Проверяем доступ пользователя
    db = await _get_db()
    is_allowed = await db.is_user_allowed(telegram_id)
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    # Безопасность: не допускаем выход за пределы базы знаний
    kb_path = Path(config.LOCAL_KB_PATH).resolve()
    file_path = (kb_path / path).resolve()
    
    if not str(file_path).startswith(str(kb_path)):
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail="Указанный путь не является файлом")
    
    try:
        content = file_path.read_text(encoding="utf-8")
        return {
            "path": path,
            "name": file_path.name,
            "content": content,
            "size": file_path.stat().st_size
        }
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Файл не является текстовым")


@router.get("/files/list")
async def list_files(
    path: str = Query("", description="Путь к папке в базе знаний"),
    telegram_id: int = Depends(verify_telegram_auth)
):
    """Получить список файлов и папок в директории базы знаний"""
    from config import config
    from pathlib import Path
    
    # Проверяем доступ пользователя
    db = await _get_db()
    is_allowed = await db.is_user_allowed(telegram_id)
    if not is_allowed:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    # Безопасность
    kb_path = Path(config.LOCAL_KB_PATH).resolve()
    dir_path = (kb_path / path).resolve()
    
    if not str(dir_path).startswith(str(kb_path)):
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail="Директория не найдена")
    
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail="Указанный путь не является директорией")
    
    items = []
    for item in sorted(dir_path.iterdir()):
        # Пропускаем скрытые файлы
        if item.name.startswith("."):
            continue
        
        items.append({
            "name": item.name,
            "path": str(item.relative_to(kb_path)),
            "is_dir": item.is_dir(),
            "size": item.stat().st_size if item.is_file() else None
        })
    
    return {
        "path": path,
        "items": items,
        "total": len(items)
    }

