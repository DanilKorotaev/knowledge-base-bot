"""
Сервис для работы с Cursor CLI
"""
import asyncio
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)


class CursorCLIService:
    """Сервис для работы с Cursor CLI"""
    
    def __init__(self, kb_path: Optional[Path] = None):
        self.kb_path = kb_path or config.LOCAL_KB_PATH
        self.api_key = config.CURSOR_API_KEY or config.OPENAI_API_KEY
        self.model = config.CURSOR_MODEL
    
    async def process_query(
        self,
        query: str,
        session_id: Optional[int] = None,
        model: Optional[str] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Обработать запрос через Cursor CLI
        
        Returns:
            tuple: (ответ от AI, список изменений файлов)
        """
        # TODO: Реализовать вызов Cursor CLI через subprocess
        # 1. Использовать cursor-agent -p --force для неинтерактивного режима
        # 2. Передать API ключ через переменную окружения
        # 3. Указать модель через --model (опционально)
        # 4. Работать в директории локальной копии базы знаний
        # 5. Отследить изменения файлов (до/после выполнения)
        
        logger.info(f"Обработка запроса через Cursor CLI: {query[:50]}...")
        
        # Временная заглушка
        response = f"Запрос получен: {query}\n\nОбработка через Cursor CLI будет реализована позже."
        changes = []
        
        return response, changes
    
    async def get_file_changes(self) -> List[Dict[str, Any]]:
        """Получить список измененных файлов (через git diff)"""
        # TODO: Реализовать получение изменений через git diff
        return []
    
    def setup_cursor_rules(self, kb_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Создать структуру .cursor/rules/ с системными промптами
        
        Args:
            kb_config: Конфигурация БЗ (опционально, для универсальности)
        """
        rules_dir = self.kb_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Специальный промпт для Telegram бота (универсальный)
        bot_prompt = rules_dir / "telegram-bot-prompt.md"
        if not bot_prompt.exists():
            bot_prompt.write_text("""# Системный промпт для Telegram-бота

Ты - AI-ассистент, работающий внутри Telegram-бота для взаимодействия с базой знаний.

## О боте
- Название: Telegram Knowledge Base Bot
- Назначение: Интерфейс между пользователем и базой знаний через Telegram

## Как ты работаешь
1. Пользователь отправляет запрос в Telegram бота
2. Бот передает запрос тебе через Cursor CLI
3. Ты обрабатываешь запрос с учетом контекста базы знаний
4. Ты можешь читать, искать и изменять файлы в базе знаний
5. Результат возвращается пользователю через бота

## Формат ответа
- Отвечай на русском языке (или языке пользователя)
- Используй Markdown форматирование
- Будь кратким, но информативным

## Контекст базы знаний
База знаний находится в этой директории. Структура и правила работы описаны в:
- Системных промптах в `.cursor/rules/`
- Документации базы знаний (если есть)
- Файлах конфигурации (если есть)
""")
        
        # Если есть конфигурация БЗ, создать специфичный промпт
        if kb_config:
            kb_specific = rules_dir / "knowledge-base-config.md"
            import json
            kb_specific.write_text(f"""# Конфигурация базы знаний

{json.dumps(kb_config, indent=2, ensure_ascii=False)}
""")

