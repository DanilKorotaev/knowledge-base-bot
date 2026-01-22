"""
Помощники для работы с сообщениями
"""
import logging
import re
from typing import List, Optional, Dict, Any
from aiogram.types import Message, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    """
    Экранировать специальные символы для Markdown V2
    
    Args:
        text: Текст для экранирования
    
    Returns:
        str: Экранированный текст
    """
    # Символы, которые нужно экранировать в Markdown V2
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text


def markdown_to_html(text: str) -> str:
    """
    Конвертировать Markdown в HTML для Telegram
    
    Args:
        text: Текст в Markdown формате
    
    Returns:
        str: Текст в HTML формате
    """
    # Экранировать HTML специальные символы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Заголовки
    text = re.sub(r'^### (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)
    
    # Жирный текст
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Курсив
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    # Код (inline)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    
    # Код (блок)
    text = re.sub(r'```(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    
    # Списки
    text = re.sub(r'^\- (.*?)$', r'• \1', text, flags=re.MULTILINE)
    
    return text


def split_long_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Разбить длинное сообщение на части
    
    Args:
        text: Текст сообщения
        max_length: Максимальная длина части (по умолчанию 4096 для Telegram)
    
    Returns:
        List[str]: Список частей сообщения
    """
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    
    for line in text.split("\n"):
        if len(current_part) + len(line) + 1 > max_length:
            if current_part:
                parts.append(current_part)
                current_part = line
            else:
                # Строка слишком длинная, разбиваем по словам
                words = line.split()
                for word in words:
                    if len(current_part) + len(word) + 1 > max_length:
                        if current_part:
                            parts.append(current_part)
                            current_part = word
                        else:
                            # Слово слишком длинное, разбиваем посимвольно
                            parts.append(word[:max_length])
                            current_part = word[max_length:]
                    else:
                        current_part += " " + word if current_part else word
        else:
            current_part += "\n" + line if current_part else line
    
    if current_part:
        parts.append(current_part)
    
    return parts


async def send_formatted_message(
    message: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> None:
    """
    Отправить форматированное сообщение с автоматическим fallback
    
    Пытается отправить сообщение в следующем порядке:
    1. HTML форматирование
    2. Markdown V2 форматирование
    3. Plain text (без форматирования)
    
    Args:
        message: Объект сообщения Telegram
        text: Текст для отправки
        reply_markup: Опциональная клавиатура
    """
    # Разбить длинные сообщения на части
    response_parts = split_long_message(text, max_length=4000)
    
    for part in response_parts:
        try:
            # Попытка 1: HTML форматирование
            html_part = markdown_to_html(part)
            await message.answer(html_part, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            reply_markup = None  # Клавиатуру показываем только в первом сообщении
        except TelegramBadRequest as e:
            logger.warning(f"Ошибка форматирования HTML: {e}, пробую Markdown V2")
            try:
                # Попытка 2: Markdown V2 форматирование
                md_part = escape_markdown_v2(part)
                await message.answer(md_part, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=reply_markup)
                reply_markup = None
            except TelegramBadRequest as e2:
                logger.warning(f"Ошибка форматирования Markdown V2: {e2}, отправляю без форматирования")
                # Попытка 3: Plain text
                await message.answer(part, reply_markup=reply_markup)
                reply_markup = None


def format_file_changes_info(changes: List[Dict[str, Any]], sync_success: bool) -> str:
    """
    Форматировать информацию об изменениях файлов
    
    Args:
        changes: Список изменений файлов
        sync_success: Успешна ли синхронизация с NextCloud
    
    Returns:
        str: Отформатированная строка с информацией об изменениях
    """
    if not changes:
        return ""
    
    changes_info = f"\n\n📝 Изменено файлов: {len(changes)}"
    
    if len(changes) <= 5:
        changes_list = "\n".join([f"  • {ch.get('path', 'unknown')}" for ch in changes])
        changes_info += f"\n{changes_list}"
    else:
        changes_list = "\n".join([f"  • {ch.get('path', 'unknown')}" for ch in changes[:5]])
        changes_info += f"\n{changes_list}\n  ... и еще {len(changes) - 5}"
    
    if sync_success:
        changes_info += "\n✅ Изменения синхронизированы с NextCloud"
    else:
        changes_info += "\n⚠️ Не удалось синхронизировать с NextCloud"
    
    return changes_info

