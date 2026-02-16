"""
Сервис для работы с OpenAI API (только для Whisper)
"""
import logging
from typing import Optional
from openai import AsyncOpenAI
import httpx
from config import config

logger = logging.getLogger(__name__)


class OpenAIService:
    """Сервис для работы с OpenAI API (только для Whisper)"""
    
    def __init__(self):
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY не установлен")
        
        # Настроить HTTP-клиент с прокси (если указан)
        client_kwargs = {"api_key": config.OPENAI_API_KEY}
        if config.OPENAI_PROXY:
            logger.info(f"OpenAI API будет использовать прокси: {config.OPENAI_PROXY}")
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.OPENAI_PROXY)
        
        self.client = AsyncOpenAI(**client_kwargs)
    
    async def transcribe_audio(
        self,
        audio_file_path: str,
        language: Optional[str] = None
    ) -> dict:
        """
        Транскрибировать аудио через Whisper API
        
        Args:
            audio_file_path: Путь к аудио файлу
            language: Язык аудио (опционально)
        
        Returns:
            dict: Результат транскрибации с полями 'text' и 'language'
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language
                )
            
            # Получить язык из транскрипции, если доступен, иначе использовать переданный или "unknown"
            detected_language = getattr(transcript, 'language', None) or language or "unknown"
            
            return {
                "text": transcript.text,
                "language": detected_language
            }
        except Exception as e:
            logger.error(f"Ошибка при транскрибации: {e}", exc_info=True)
            raise

