"""
Помощники для работы с сообщениями
"""
import asyncio
import html
import logging
import re
import time
from typing import List, Optional, Dict, Any, Callable, Awaitable
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
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
    reply_markup = None
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


class StreamingMessageUpdater:
    """
    Обновляет сообщение в Telegram в реальном времени по мере получения чанков от Cursor CLI.
    
    Буферизирует текст и обновляет сообщение не чаще update_interval секунд
    и не менее min_buffer_size символов (кроме первого чанка).
    """
    
    def __init__(
        self,
        message: Message,
        typing_message: Message,
        update_interval: float = 1.5,
        min_buffer_size: int = 100,
    ):
        """
        Args:
            message: Исходное сообщение пользователя
            typing_message: Сообщение "⏳ Обрабатываю..." (будет обновляться стримом)
            update_interval: Минимальный интервал между обновлениями (секунды)
            min_buffer_size: Минимальный размер буфера для обновления
        """
        self.message = message
        self.typing_message = typing_message
        self.buffer: str = ""
        self.full_text: str = ""
        self.last_update_time: float = 0.0
        self.update_interval: float = update_interval
        self.min_buffer_size: int = min_buffer_size
        self.first_chunk: bool = True
        self._update_lock = asyncio.Lock()
    
    async def on_chunk(self, chunk: str) -> None:
        """
        Callback для получения чанка от Cursor CLI.
        
        Накапливает текст и обновляет сообщение в Telegram с буферизацией.
        
        Args:
            chunk: Очередной чанк текста от Cursor CLI
        """
        self.buffer += chunk
        self.full_text += chunk
        
        now = time.time()
        
        if self.first_chunk:
            # Первый чанк — обновляем сразу, чтобы пользователь видел начало ответа
            await self._update_message()
            self.first_chunk = False
        elif (
            len(self.buffer) >= self.min_buffer_size
            and (now - self.last_update_time) >= self.update_interval
        ):
            # Достаточно текста накопилось и прошло достаточно времени
            await self._update_message()
    
    async def _update_message(self) -> None:
        """
        Обновить сообщение в Telegram текущим содержимым full_text + курсор.
        
        - Добавляет ▌ (курсор) в конце — показывает что ответ генерируется
        - Если текст > 4000 символов — показывает хвост с ... в начале
        - parse_mode=None (plain text) — иначе незакрытые теги ломают HTML при стриминге
        - Обрабатывает ошибки Telegram (message is not modified, Flood control)
        """
        async with self._update_lock:
            display_text = self.full_text.strip()
            if not display_text:
                return
            
            # Добавить курсор
            display_text += " ▌"
            
            # Если текст слишком длинный — показать хвост
            max_display = 4000
            if len(display_text) > max_display:
                display_text = "..." + display_text[-(max_display - 3):]
            
            try:
                await self.typing_message.edit_text(display_text, parse_mode=None)
                self.last_update_time = time.time()
                self.buffer = ""
            except TelegramRetryAfter as e:
                # Flood control — увеличить интервал и подождать
                logger.warning(f"Telegram Flood control: ждём {e.retry_after}с, увеличиваем интервал")
                self.update_interval *= 2
                await asyncio.sleep(e.retry_after)
            except TelegramBadRequest as e:
                error_text = str(e)
                if "message is not modified" in error_text:
                    # Текст не изменился — игнорируем
                    pass
                elif "message to edit not found" in error_text:
                    # Сообщение удалено — прекращаем обновления
                    logger.warning("Streaming: сообщение для обновления не найдено (удалено?)")
                else:
                    logger.warning(f"Streaming: ошибка обновления сообщения: {e}")
            except Exception as e:
                logger.warning(f"Streaming: неожиданная ошибка при обновлении: {e}")
    
    async def flush(self) -> None:
        """Принудительный сброс буфера — обновить сообщение с текущим текстом."""
        if self.buffer:
            await self._update_message()
    
    async def finalize(self) -> None:
        """
        Финализировать стриминг:
        - Сбросить буфер
        - Убрать курсор ▌
        - Конвертировать полный текст в HTML через markdown_to_html()
        - Если HTML не удалось — fallback на plain text
        - Если текст > 4000 символов — разбить на несколько сообщений
        """
        # Сбросить оставшийся буфер
        await self.flush()
        
        final_text = self.full_text.strip()
        if not final_text:
            # Нечего показывать — удалить typing_message
            try:
                await self.typing_message.delete()
            except Exception:
                pass
            return
        
        # Если текст помещается в одно сообщение
        if len(final_text) <= 4000:
            await self._send_final_single(final_text)
        else:
            # Текст слишком длинный — разбить на несколько сообщений
            await self._send_final_split(final_text)
    
    async def _send_final_single(self, text: str) -> None:
        """Отправить финальный текст в одном сообщении (через edit_text)."""
        # Попытка 1: HTML
        try:
            html_text = markdown_to_html(text)
            await self.typing_message.edit_text(html_text, parse_mode=ParseMode.HTML)
            return
        except TelegramBadRequest as e:
            logger.debug(f"Streaming finalize: HTML не удался: {e}")
        except Exception as e:
            logger.debug(f"Streaming finalize: ошибка HTML: {e}")
        
        # Попытка 2: plain text
        try:
            await self.typing_message.edit_text(text, parse_mode=None)
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e):
                logger.warning(f"Streaming finalize: не удалось обновить сообщение: {e}")
        except Exception as e:
            logger.warning(f"Streaming finalize: неожиданная ошибка: {e}")
    
    async def _send_final_split(self, text: str) -> None:
        """Разбить длинный текст на несколько сообщений."""
        parts = split_long_message(text, max_length=4000)
        
        # Первую часть — через edit_text в typing_message
        first_part = parts[0]
        try:
            html_first = markdown_to_html(first_part)
            await self.typing_message.edit_text(html_first, parse_mode=ParseMode.HTML)
        except Exception:
            try:
                await self.typing_message.edit_text(first_part, parse_mode=None)
            except Exception as e:
                logger.warning(f"Streaming finalize split: не удалось обновить первую часть: {e}")
        
        # Остальные части — новыми сообщениями
        for part in parts[1:]:
            try:
                html_part = markdown_to_html(part)
                await self.message.answer(html_part, parse_mode=ParseMode.HTML)
            except Exception:
                try:
                    await self.message.answer(part, parse_mode=None)
                except Exception as e:
                    logger.warning(f"Streaming finalize split: не удалось отправить часть: {e}")


def format_file_changes_info(
    changes: List[Dict[str, Any]],
    sync_success: bool,
    file_urls: Optional[Dict[str, str]] = None,
    link_mode: str = "share"
) -> str:
    """
    Форматировать информацию об изменениях файлов (HTML формат)
    
    Args:
        changes: Список изменений файлов
        sync_success: Успешна ли синхронизация с NextCloud
        file_urls: Словарь {путь_файла: URL} для кликабельных ссылок (опционально)
        link_mode: Режим ссылок ("share" | "direct" | "disabled")
    
    Returns:
        str: HTML строка с информацией об изменениях
    """
    if not changes:
        return ""
    
    changes_info = f"\n\n📝 Изменено файлов: {len(changes)}"
    
    display_changes = changes[:5]
    
    for ch in display_changes:
        path = ch.get('path', 'unknown')
        filename = path.rsplit('/', 1)[-1] if '/' in path else path
        escaped_path = html.escape(path)
        
        url = file_urls.get(path) if file_urls else None
        if url:
            link_icon = "📎" if link_mode == "share" else "🔗"
            changes_info += f"\n  • <code>{html.escape(filename)}</code>  <a href=\"{html.escape(url)}\">{link_icon} Открыть</a>"
        else:
            changes_info += f"\n  • <code>{escaped_path}</code>"
    
    if len(changes) > 5:
        changes_info += f"\n  ... и ещё {len(changes) - 5}"
    
    if sync_success:
        changes_info += "\n✅ Изменения синхронизированы с NextCloud"
    else:
        changes_info += "\n⚠️ Не удалось синхронизировать с NextCloud"
    
    if file_urls and link_mode == "direct":
        changes_info += "\n⚠️ Ссылки требуют авторизации в NextCloud"
    
    return changes_info

