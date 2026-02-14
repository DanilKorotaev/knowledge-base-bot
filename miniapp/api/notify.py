"""
Отправка уведомлений в Telegram-чат из Mini App
"""
import logging
import httpx

logger = logging.getLogger(__name__)


async def send_chat_notification(telegram_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """
    Отправить сообщение пользователю в Telegram-чат от имени бота.
    
    Используется для уведомлений при действиях в Mini App
    (переключение/завершение/удаление сессий).
    
    Args:
        telegram_id: Telegram ID пользователя (= chat_id для личных сообщений)
        text: Текст сообщения
        parse_mode: Режим форматирования (HTML / Markdown)
    
    Returns:
        True если сообщение отправлено успешно
    """
    from config import config
    
    if not config.TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN не установлен, уведомление не отправлено")
        return False
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                logger.info(f"Уведомление отправлено пользователю {telegram_id}")
                return True
            else:
                logger.warning(
                    f"Ошибка отправки уведомления: {response.status_code} — {response.text}"
                )
                return False
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю {telegram_id}: {e}")
        return False

