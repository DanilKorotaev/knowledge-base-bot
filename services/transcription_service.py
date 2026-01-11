"""
Сервис для транскрибации голосовых сообщений
"""
import logging
from pathlib import Path
from typing import Optional
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Сервис для транскрибации голосовых сообщений"""
    
    def __init__(self, openai_service: OpenAIService):
        self.openai_service = openai_service
    
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

