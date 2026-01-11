"""
Помощники для работы с сообщениями
"""
from typing import List
from aiogram.types import Message


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

