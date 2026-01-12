"""
Помощники для работы с сообщениями
"""
import re
from typing import List
from aiogram.types import Message


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

