"""
Конфигурация бота
"""
import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Загрузить переменные окружения
load_dotenv()


class Config:
    """Конфигурация приложения"""
    
    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
    
    # Cursor CLI / OpenAI API
    CURSOR_API_KEY: Optional[str] = os.getenv("CURSOR_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    # Модель для Cursor CLI: "auto" = автовыбор, или конкретная модель (gpt-4o, claude-sonnet, etc.)
    CURSOR_MODEL: str = os.getenv("CURSOR_MODEL", "auto")
    
    # NextCloud
    NEXTCLOUD_URL: Optional[str] = os.getenv("NEXTCLOUD_URL")
    NEXTCLOUD_BOT_USERNAME: Optional[str] = os.getenv("NEXTCLOUD_BOT_USERNAME")
    NEXTCLOUD_BOT_PASSWORD: Optional[str] = os.getenv("NEXTCLOUD_BOT_PASSWORD")
    NEXTCLOUD_KNOWLEDGE_BASE_PATH: str = os.getenv("NEXTCLOUD_KNOWLEDGE_BASE_PATH", "/KnowledgeBase")
    
    # Local Knowledge Base
    LOCAL_KB_PATH: Path = Path(os.getenv("LOCAL_KB_PATH", "/var/knowledge-base-bot/kb"))
    SYNC_INTERVAL: int = int(os.getenv("SYNC_INTERVAL", "300"))
    AUTO_SYNC: bool = os.getenv("AUTO_SYNC", "true").lower() == "true"
    ENABLE_SYNC: bool = os.getenv("ENABLE_SYNC", "false").lower() == "true"
    SYNC_DELETE_MISSING: bool = os.getenv("SYNC_DELETE_MISSING", "true").lower() == "true"  # Удалять файлы при синхронизации
    
    # Database
    DB_TYPE: str = os.getenv("DB_TYPE", "postgresql")  # postgresql или sqlite
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "knowledge_base_bot")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_FILE: Optional[str] = os.getenv("DB_FILE")  # Для SQLite
    
    # Bot settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_SESSION_MESSAGES: int = int(os.getenv("MAX_SESSION_MESSAGES", "50"))
    MAX_ATTACHMENTS_PER_MESSAGE: int = int(os.getenv("MAX_ATTACHMENTS_PER_MESSAGE", "5"))
    ENABLE_CHANGE_TRACKING: bool = os.getenv("ENABLE_CHANGE_TRACKING", "true").lower() == "true"
    
    # Streaming
    STREAMING_ENABLED: bool = os.getenv("STREAMING_ENABLED", "true").lower() in ("true", "1", "yes")
    STREAMING_UPDATE_INTERVAL: float = float(os.getenv("STREAMING_UPDATE_INTERVAL", "1.5"))
    STREAMING_MIN_BUFFER: int = int(os.getenv("STREAMING_MIN_BUFFER", "100"))
    
    # Mini App
    MINIAPP_URL: Optional[str] = os.getenv("MINIAPP_URL")  # URL для Telegram Web App (HTTPS обязателен)
    MINIAPP_PORT: int = int(os.getenv("MINIAPP_PORT", "8080"))
    MINIAPP_HOST: str = os.getenv("MINIAPP_HOST", "0.0.0.0")
    
    # Access control
    ACCESS_MODE: str = os.getenv("ACCESS_MODE", "restricted")  # "open" or "restricted"
    ADMIN_TELEGRAM_IDS: List[int] = [
        int(id.strip()) for id in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",")
        if id.strip()
    ]
    
    @classmethod
    def validate(cls) -> bool:
        """Проверка обязательных параметров"""
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN не установлен")
        
        if not cls.CURSOR_API_KEY and not cls.OPENAI_API_KEY:
            raise ValueError("Необходимо установить CURSOR_API_KEY или OPENAI_API_KEY")
        
        # Валидация режима доступа
        if cls.ACCESS_MODE not in ["open", "restricted"]:
            raise ValueError(f"ACCESS_MODE должен быть 'open' или 'restricted', получено: {cls.ACCESS_MODE}")
        
        return True
    
    @classmethod
    def is_dev_mode(cls) -> bool:
        """Проверка режима разработки"""
        return cls.DB_TYPE == "sqlite" or not cls.ENABLE_SYNC


# Создать экземпляр конфигурации
config = Config()

