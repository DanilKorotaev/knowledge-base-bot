"""
Сервис для транскрибации голосовых сообщений
"""
import logging
from pathlib import Path
from typing import Optional
from config import config
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

# Кэш шаблона промпта (на уровне модуля, чтобы не читать файл каждый раз)
_polish_prompt_cache: Optional[str] = None


def _load_polish_prompt() -> str:
    """
    Загрузить шаблон промпта для полировки транскрипции.
    
    Приоритет загрузки:
    1. Путь из переменной окружения TRANSCRIPTION_POLISH_PROMPT_PATH (если указан)
    2. Файл из проекта: agent/transcription_polish_prompt.md
    3. Встроенный fallback
    
    Returns:
        str: Шаблон промпта с плейсхолдерами {language} и {text}
    """
    global _polish_prompt_cache
    if _polish_prompt_cache is not None:
        return _polish_prompt_cache
    
    # 1. Проверяем переменную окружения
    custom_path = config.TRANSCRIPTION_POLISH_PROMPT_PATH
    if custom_path:
        prompt_path = Path(custom_path)
        if not prompt_path.is_absolute():
            project_root = Path(__file__).parent.parent
            prompt_path = project_root / prompt_path
        if prompt_path.exists():
            _polish_prompt_cache = prompt_path.read_text(encoding="utf-8")
            logger.info(f"Загружен промпт полировки из указанного пути: {prompt_path}")
            return _polish_prompt_cache
        else:
            logger.warning(f"Указанный путь к промпту полировки не найден: {prompt_path}")
    
    # 2. Загрузить из проекта
    project_root = Path(__file__).parent.parent
    default_path = project_root / "agent" / "transcription_polish_prompt.md"
    if default_path.exists():
        _polish_prompt_cache = default_path.read_text(encoding="utf-8")
        logger.info(f"Загружен промпт полировки из проекта: {default_path}")
        return _polish_prompt_cache
    
    # 3. Fallback — встроенный промпт
    logger.warning("Файл промпта полировки не найден, используется встроенный промпт")
    _polish_prompt_cache = (
        "Ты получаешь расшифровку голосового сообщения. Преобразуй её в чистый, грамотный текст:\n"
        "- Расставь правильную пунктуацию\n"
        "- Исправь капитализацию\n"
        "- Удали слова-паразиты и оговорки\n"
        "- Удали повторы и самоисправления\n"
        "- НЕ меняй смысл, НЕ добавляй информацию, НЕ перефразируй\n"
        "- Верни ТОЛЬКО исправленный текст, без пояснений\n\n"
        "Язык: {language}\n\n"
        "Текст:\n{text}"
    )
    return _polish_prompt_cache


class TranscriptionService:
    """Сервис для транскрибации голосовых сообщений"""
    
    def __init__(self, openai_service: OpenAIService, cursor_cli_service=None):
        self.openai_service = openai_service
        self.cursor_cli_service = cursor_cli_service
    
    async def polish_transcription(
        self,
        text: str,
        language: Optional[str] = None
    ) -> str:
        """
        Постобработка транскрипции через LLM — полировка текста.
        Требует CursorCLIService в конструкторе.
        
        Args:
            text: Сырой текст транскрипции
            language: Язык текста (из Whisper)
        
        Returns:
            str: Отполированный текст (или оригинальный при ошибке)
        """
        if not config.TRANSCRIPTION_POLISH_ENABLED:
            logger.debug("Полировка транскрипции отключена (TRANSCRIPTION_POLISH_ENABLED=false)")
            return text
        
        if not self.cursor_cli_service:
            logger.warning("CursorCLIService не передан в TranscriptionService, полировка невозможна")
            return text
        
        if not text or not text.strip():
            return text
        
        # Загрузить шаблон промпта и подставить значения
        prompt_template = _load_polish_prompt()
        prompt = prompt_template.format(
            language=language or "auto",
            text=text
        )
        
        logger.info(f"Полировка транскрипции: {len(text)} символов, язык: {language or 'auto'}")
        
        try:
            polished = await self.cursor_cli_service.run_simple_prompt(
                prompt=prompt,
                model=config.TRANSCRIPTION_POLISH_MODEL,
                timeout=60
            )
            
            if polished and polished.strip():
                logger.info(
                    f"Полировка завершена: {len(text)} → {len(polished)} символов"
                )
                return polished.strip()
            else:
                logger.warning("Полировка вернула пустой результат, возвращаем оригинал")
                return text
                
        except Exception as e:
            logger.error(f"Ошибка при полировке транскрипции: {e}", exc_info=True)
            return text
    
    @staticmethod
    async def polish_transcription_simple(
        text: str,
        language: Optional[str] = None
    ) -> str:
        """
        Лёгкая полировка транскрипции — без полной инициализации CursorCLIService.
        
        Создаёт минимальный экземпляр CursorCLIService только для run_simple_prompt(),
        пропуская тяжёлую инициализацию (загрузка промптов БЗ, копирование cursor rules).
        
        Args:
            text: Сырой текст транскрипции
            language: Язык текста (из Whisper)
        
        Returns:
            str: Отполированный текст (или оригинальный при ошибке)
        """
        if not config.TRANSCRIPTION_POLISH_ENABLED:
            logger.debug("Полировка транскрипции отключена (TRANSCRIPTION_POLISH_ENABLED=false)")
            return text
        
        if not text or not text.strip():
            return text
        
        api_key = config.CURSOR_API_KEY or config.OPENAI_API_KEY
        if not api_key:
            logger.warning("API ключ не установлен, полировка невозможна")
            return text
        
        # Загрузить шаблон промпта и подставить значения
        prompt_template = _load_polish_prompt()
        prompt = prompt_template.format(
            language=language or "auto",
            text=text
        )
        
        logger.info(f"Полировка транскрипции: {len(text)} символов, язык: {language or 'auto'}")
        
        try:
            # Лёгкая инициализация: создаём объект без __init__ и задаём только нужные поля
            from .cursor_cli_service import CursorCLIService
            service = object.__new__(CursorCLIService)
            service.api_key = api_key
            service.kb_path = config.LOCAL_KB_PATH
            service.model = config.CURSOR_MODEL
            
            polished = await service.run_simple_prompt(
                prompt=prompt,
                model=config.TRANSCRIPTION_POLISH_MODEL,
                timeout=60
            )
            
            if polished and polished.strip():
                logger.info(
                    f"Полировка завершена: {len(text)} → {len(polished)} символов"
                )
                return polished.strip()
            else:
                logger.warning("Полировка вернула пустой результат, возвращаем оригинал")
                return text
                
        except Exception as e:
            logger.error(f"Ошибка при полировке транскрипции: {e}", exc_info=True)
            return text
    
    async def transcribe(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> dict:
        """
        Транскрибировать аудио файл
        
        Args:
            audio_file_path: Путь к аудио файлу
            language: Язык аудио (опционально)
        
        Returns:
            dict: Результат транскрибации
        """
        return await self.openai_service.transcribe_audio(audio_file_path, language)
