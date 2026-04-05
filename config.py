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
    TELEGRAM_PROXY: Optional[str] = os.getenv("TELEGRAM_PROXY")  # SOCKS5/HTTP прокси для Telegram API (например socks5://host.docker.internal:1080)
    
    # Cursor CLI / OpenAI API
    CURSOR_API_KEY: Optional[str] = os.getenv("CURSOR_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_PROXY: Optional[str] = os.getenv("OPENAI_PROXY")  # SOCKS5/HTTP прокси для OpenAI API (например socks5://127.0.0.1:1080)
    # Прокси для cursor-agent (если не задан — используется OPENAI_PROXY): ALL_PROXY/HTTPS_PROXY в subprocess
    CURSOR_CLI_PROXY: Optional[str] = os.getenv("CURSOR_CLI_PROXY")
    # Модель для Cursor CLI: "auto" = автовыбор, или конкретная модель (gpt-4o, claude-sonnet, etc.)
    CURSOR_MODEL: str = os.getenv("CURSOR_MODEL", "auto")
    
    # NextCloud
    NEXTCLOUD_URL: Optional[str] = os.getenv("NEXTCLOUD_URL")
    NEXTCLOUD_BOT_USERNAME: Optional[str] = os.getenv("NEXTCLOUD_BOT_USERNAME")
    NEXTCLOUD_BOT_PASSWORD: Optional[str] = os.getenv("NEXTCLOUD_BOT_PASSWORD")
    NEXTCLOUD_KNOWLEDGE_BASE_PATH: str = os.getenv("NEXTCLOUD_KNOWLEDGE_BASE_PATH", "/KnowledgeBase")
    
    # NextCloud Web Links
    NEXTCLOUD_WEB_URL: Optional[str] = os.getenv("NEXTCLOUD_WEB_URL")  # Fallback на NEXTCLOUD_URL
    NEXTCLOUD_LINK_MODE: str = os.getenv("NEXTCLOUD_LINK_MODE", "disabled")  # "share" | "direct" | "disabled"
    NEXTCLOUD_SHARE_EXPIRATION_HOURS: int = int(os.getenv("NEXTCLOUD_SHARE_EXPIRATION_HOURS", "24"))
    
    # Local Knowledge Base
    LOCAL_KB_PATH: Path = Path(os.getenv("LOCAL_KB_PATH", "/var/knowledge-base-bot/kb"))
    SYNC_INTERVAL: int = int(os.getenv("SYNC_INTERVAL", "300"))
    AUTO_SYNC: bool = os.getenv("AUTO_SYNC", "true").lower() == "true"
    ENABLE_SYNC: bool = os.getenv("ENABLE_SYNC", "false").lower() == "true"
    SYNC_DELETE_MISSING: bool = os.getenv("SYNC_DELETE_MISSING", "true").lower() == "true"  # Удалять файлы при синхронизации
    
    # Паттерны исключений при синхронизации (через запятую)
    # Каждый паттерн проверяется как подстрока в пути файла или как имя файла/директории
    SYNC_EXCLUDE_PATTERNS: List[str] = [
        p.strip() for p in os.getenv(
            "SYNC_EXCLUDE_PATTERNS",
            ".git/,.git\\,__pycache__/,__pycache__\\,node_modules/,node_modules\\,.DS_Store,.env,.venv/,venv/,.idea/,.vscode/"
        ).split(",")
        if p.strip()
    ]
    
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
    
    # Transcription polish (постобработка транскрипции через LLM)
    TRANSCRIPTION_POLISH_ENABLED: bool = os.getenv("TRANSCRIPTION_POLISH_ENABLED", "true").lower() in ("true", "1", "yes")
    TRANSCRIPTION_POLISH_MODEL: str = os.getenv("TRANSCRIPTION_POLISH_MODEL", "auto")
    TRANSCRIPTION_POLISH_PROMPT_PATH: Optional[str] = os.getenv("TRANSCRIPTION_POLISH_PROMPT_PATH")  # Путь к файлу промпта (по умолчанию agent/transcription_polish_prompt.md)
    
    # Streaming
    STREAMING_ENABLED: bool = os.getenv("STREAMING_ENABLED", "true").lower() in ("true", "1", "yes")
    STREAMING_UPDATE_INTERVAL: float = float(os.getenv("STREAMING_UPDATE_INTERVAL", "1.5"))
    STREAMING_MIN_BUFFER: int = int(os.getenv("STREAMING_MIN_BUFFER", "100"))
    # Обновление текста «Обрабатываю запрос...» с таймером (секунды)
    QUERY_PROGRESS_TIMER_INTERVAL: int = int(os.getenv("QUERY_PROGRESS_TIMER_INTERVAL", "15"))
    
    # KB App API (iOS) — отдельный процесс `uvicorn kb_app_api.main:app`
    KB_APP_API_TOKEN: Optional[str] = os.getenv("KB_APP_API_TOKEN")
    KB_APP_API_TELEGRAM_ID: int = int(os.getenv("KB_APP_API_TELEGRAM_ID", "9000000009000001"))
    # POST /api/auth/token — выдача того же Bearer после проверки секрета (см. kb_app_api/routes/auth.py)
    KB_APP_API_TOKEN_ENDPOINT_ENABLED: bool = os.getenv(
        "KB_APP_API_TOKEN_ENDPOINT_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    KB_APP_API_TOKEN_ISSUE_SECRET: Optional[str] = os.getenv("KB_APP_API_TOKEN_ISSUE_SECRET")
    
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

