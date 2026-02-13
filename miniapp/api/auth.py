"""
Аутентификация через Telegram Web App initData
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Optional
from urllib.parse import parse_qs, unquote

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> Optional[dict]:
    """
    Валидация Telegram Web App initData
    
    Проверяет подпись данных от Telegram Web App по алгоритму:
    1. Разбираем строку initData на параметры
    2. Собираем data_check_string из всех параметров кроме hash
    3. Вычисляем secret_key = HMAC-SHA256("WebAppData", bot_token)
    4. Вычисляем hash = HMAC-SHA256(secret_key, data_check_string)
    5. Сравниваем с полученным hash
    
    Args:
        init_data: Строка initData от Telegram Web App
        bot_token: Токен бота
        max_age: Максимальный возраст данных в секундах (по умолчанию 24 часа)
    
    Returns:
        dict с данными пользователя или None если невалидно
    """
    if not init_data:
        return None
    
    try:
        # Разбираем параметры
        parsed = parse_qs(init_data, keep_blank_values=True)
        
        # Получаем hash
        received_hash = parsed.get("hash", [None])[0]
        if not received_hash:
            logger.warning("initData не содержит hash")
            return None
        
        # Проверяем auth_date
        auth_date_str = parsed.get("auth_date", [None])[0]
        if auth_date_str:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > max_age:
                logger.warning(f"initData устарела: auth_date={auth_date}")
                return None
        
        # Собираем data_check_string
        # Сортируем все параметры кроме hash в алфавитном порядке
        check_pairs = []
        for key in sorted(parsed.keys()):
            if key == "hash":
                continue
            value = parsed[key][0]
            check_pairs.append(f"{key}={value}")
        
        data_check_string = "\n".join(check_pairs)
        
        # Вычисляем secret_key
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        # Вычисляем hash
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Сравниваем
        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("initData hash не совпадает")
            return None
        
        # Извлекаем данные пользователя
        user_data_str = parsed.get("user", [None])[0]
        if user_data_str:
            user_data = json.loads(unquote(user_data_str))
            return user_data
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка валидации initData: {e}", exc_info=True)
        return None


async def verify_telegram_auth(
    x_telegram_init_data: str = Header(None, alias="X-Telegram-Init-Data")
) -> int:
    """
    FastAPI dependency для аутентификации через Telegram initData
    
    Returns:
        int: Telegram ID пользователя
    
    Raises:
        HTTPException: Если аутентификация не пройдена
    """
    import sys
    import os
    
    # Добавляем корень проекта в sys.path для импорта config
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    from config import config
    
    if not x_telegram_init_data:
        raise HTTPException(
            status_code=401,
            detail="Отсутствует заголовок X-Telegram-Init-Data"
        )
    
    user_data = validate_init_data(x_telegram_init_data, config.TELEGRAM_TOKEN)
    
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Невалидные данные аутентификации"
        )
    
    user_id = user_data.get("id")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Не удалось определить ID пользователя"
        )
    
    return int(user_id)

