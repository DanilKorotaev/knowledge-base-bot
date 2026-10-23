"""
Конфигурация бота
"""
import os
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# Загрузить переменные окружения
load_dotenv()


def _parse_host_allowlist(raw: str, *, defaults: Optional[List[str]] = None) -> List[str]:
    """Comma-separated hostnames/IPs (no schemes, no paths)."""
    items = [
        h.strip().lower()
        for h in (raw or "").split(",")
        if h.strip()
    ]
    if items:
        return items
    return list(defaults or [])


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
    # Модель для Cursor CLI: "auto"/"default" → --model auto (пул Auto); иначе --model как есть
    CURSOR_MODEL: str = os.getenv("CURSOR_MODEL", "auto")
    
    # NextCloud — два независимых URL (могут совпадать или различаться):
    # NEXTCLOUD_URL     — API для бота: WebDAV sync + OCS (создание share). Можно http://127.0.0.1:8080 на mini.
    # NEXTCLOUD_WEB_URL — публичная база для ссылок пользователю (direct /f/… и rewrite localhost из OCS).
    #                     Если не задан → fallback на NEXTCLOUD_URL.
    # Share-ссылки (LINK_MODE=share): URL в основном из ответа OCS (overwritehost на NC);
    # если OCS вернул localhost — подменяем хост на NEXTCLOUD_WEB_URL.
    # Не путать с KB_APP_PUBLIC_BASE_URL (шаринг чатов KB App).
    NEXTCLOUD_URL: Optional[str] = os.getenv("NEXTCLOUD_URL")
    NEXTCLOUD_BOT_USERNAME: Optional[str] = os.getenv("NEXTCLOUD_BOT_USERNAME")
    NEXTCLOUD_BOT_PASSWORD: Optional[str] = os.getenv("NEXTCLOUD_BOT_PASSWORD")
    NEXTCLOUD_KNOWLEDGE_BASE_PATH: str = os.getenv("NEXTCLOUD_KNOWLEDGE_BASE_PATH", "/KnowledgeBase")

    NEXTCLOUD_WEB_URL: Optional[str] = os.getenv("NEXTCLOUD_WEB_URL")
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
            ".git/,.git\\,__pycache__/,__pycache__\\,node_modules/,node_modules\\,"
            ".DS_Store,.env,.venv/,venv/,.idea/,.vscode/,"
            "fastlane/test_output/,fastlane/build_logs/,fastlane/screenshots/,"
            "vendor/bundle/,DerivedData/,build/",
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
    MAX_ATTACHMENTS_PER_MESSAGE: int = int(os.getenv("MAX_ATTACHMENTS_PER_MESSAGE", "10"))
    ENABLE_CHANGE_TRACKING: bool = os.getenv("ENABLE_CHANGE_TRACKING", "true").lower() == "true"
    
    # Transcription polish (постобработка транскрипции через LLM)
    TRANSCRIPTION_POLISH_ENABLED: bool = os.getenv("TRANSCRIPTION_POLISH_ENABLED", "true").lower() in ("true", "1", "yes")
    TRANSCRIPTION_POLISH_MODEL: str = os.getenv("TRANSCRIPTION_POLISH_MODEL", "auto")
    TRANSCRIPTION_POLISH_PROMPT_PATH: Optional[str] = os.getenv("TRANSCRIPTION_POLISH_PROMPT_PATH")  # Путь к файлу промпта (по умолчанию agent/transcription_polish_prompt.md)

    # Auto session display title after first Q&A (KB App / bot)
    SESSION_TITLE_ENABLED: bool = os.getenv("SESSION_TITLE_ENABLED", "true").lower() in ("true", "1", "yes")
    SESSION_TITLE_MODEL: str = os.getenv("SESSION_TITLE_MODEL") or os.getenv("TRANSCRIPTION_POLISH_MODEL", "auto")
    SESSION_TITLE_TIMEOUT_SEC: float = float(os.getenv("SESSION_TITLE_TIMEOUT_SEC", "45"))
    
    # Streaming
    STREAMING_ENABLED: bool = os.getenv("STREAMING_ENABLED", "true").lower() in ("true", "1", "yes")
    STREAMING_UPDATE_INTERVAL: float = float(os.getenv("STREAMING_UPDATE_INTERVAL", "1.5"))
    STREAMING_MIN_BUFFER: int = int(os.getenv("STREAMING_MIN_BUFFER", "100"))
    # Обновление текста «Обрабатываю запрос...» с таймером (секунды)
    QUERY_PROGRESS_TIMER_INTERVAL: int = int(os.getenv("QUERY_PROGRESS_TIMER_INTERVAL", "15"))

    # Cursor CLI stdout format: text | stream-json (NDJSON events + tool progress)
    CURSOR_CLI_OUTPUT_FORMAT: str = os.getenv("CURSOR_CLI_OUTPUT_FORMAT", "stream-json")
    CURSOR_CLI_STREAM_PARTIAL_OUTPUT: bool = os.getenv(
        "CURSOR_CLI_STREAM_PARTIAL_OUTPUT", "false"
    ).lower() in ("true", "1", "yes")
    
    # KB App API (iOS) — отдельный процесс `uvicorn kb_app_api.main:app`
    KB_APP_API_TOKEN: Optional[str] = os.getenv("KB_APP_API_TOKEN")
    KB_APP_API_TELEGRAM_ID: int = int(os.getenv("KB_APP_API_TELEGRAM_ID", "9000000009000001"))
    # iOS E2E / интеграционные тесты: запросы с заголовком X-KB-App-E2E: 1
    KB_APP_API_TEST_TELEGRAM_ID: int = int(
        os.getenv("KB_APP_API_TEST_TELEGRAM_ID", "9000000009000001")
    )
    # POST /api/auth/token — выдача того же Bearer после проверки секрета (см. kb_app_api/routes/auth.py)
    KB_APP_API_TOKEN_ENDPOINT_ENABLED: bool = os.getenv(
        "KB_APP_API_TOKEN_ENDPOINT_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    KB_APP_API_TOKEN_ISSUE_SECRET: Optional[str] = os.getenv("KB_APP_API_TOKEN_ISSUE_SECRET")
    # Только для отладки: не проверять is_allowed у KB_APP_API_TELEGRAM_ID при ACCESS_MODE=restricted
    KB_APP_API_BYPASS_ACCESS_CHECK: bool = os.getenv(
        "KB_APP_API_BYPASS_ACCESS_CHECK", "false"
    ).lower() in ("true", "1", "yes")

    # Structured UI (backend-driven JSON screens for iOS)
    STRUCTURED_UI_AGENT_ENABLED: bool = os.getenv(
        "STRUCTURED_UI_AGENT_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    STRUCTURED_UI_AGENT_MOCK_FALLBACK: bool = os.getenv(
        "STRUCTURED_UI_AGENT_MOCK_FALLBACK", "true"
    ).lower() in ("true", "1", "yes")
    STRUCTURED_UI_AGENT_MODEL: str = os.getenv("STRUCTURED_UI_AGENT_MODEL", "")
    STRUCTURED_UI_AGENT_TIMEOUT: int = int(os.getenv("STRUCTURED_UI_AGENT_TIMEOUT", "90"))
    STRUCTURED_UI_AGENT_PROMPT_PATH: Optional[str] = os.getenv("STRUCTURED_UI_AGENT_PROMPT_PATH")
    # Attach optional Interactive UI panels to normal chat replies (second lightweight prompt).
    STRUCTURED_UI_IN_REPLIES_ENABLED: bool = os.getenv(
        "STRUCTURED_UI_IN_REPLIES_ENABLED",
        os.getenv("STRUCTURED_UI_AGENT_ENABLED", "false"),
    ).lower() in ("true", "1", "yes")
    STRUCTURED_UI_REPLY_SUGGEST_TIMEOUT: int = int(
        os.getenv("STRUCTURED_UI_REPLY_SUGGEST_TIMEOUT", "45")
    )

    # Background Cursor jobs (separate process from uvicorn; SSE proxies job events)
    KB_APP_QUERY_JOBS_ENABLED: bool = os.getenv(
        "KB_APP_QUERY_JOBS_ENABLED", "false"
    ).lower() in ("true", "1", "yes")
    MAX_CONCURRENT_QUERY_JOBS: int = int(os.getenv("MAX_CONCURRENT_QUERY_JOBS", "2"))
    QUERY_JOB_EVENT_POLL_MS: int = int(os.getenv("QUERY_JOB_EVENT_POLL_MS", "100"))
    QUERY_JOB_STALE_RUNNING_SEC: int = int(os.getenv("QUERY_JOB_STALE_RUNNING_SEC", "1800"))

    # Public share links (read-only chat URLs; do not put the API bearer in these links)
    KB_APP_PUBLIC_BASE_URL: Optional[str] = os.getenv("KB_APP_PUBLIC_BASE_URL")
    KB_APP_SHARE_DEFAULT_TTL_DAYS: int = int(os.getenv("KB_APP_SHARE_DEFAULT_TTL_DAYS", "30"))

    # Remote boards: comma-separated hostnames allowed for remote_structured_ui provider
    BOARDS_REMOTE_HOST_ALLOWLIST: List[str] = [
        h.strip().lower()
        for h in os.getenv("BOARDS_REMOTE_HOST_ALLOWLIST", "").split(",")
        if h.strip()
    ]
    BOARDS_REMOTE_TIMEOUT_SEC: float = float(os.getenv("BOARDS_REMOTE_TIMEOUT_SEC", "8"))
    # vault_script: max seconds for sandboxed build()
    BOARDS_VAULT_SCRIPT_TIMEOUT_SEC: float = float(
        os.getenv("BOARDS_VAULT_SCRIPT_TIMEOUT_SEC", "30")
    )

    # Host allowlist for GET /api/remote-ui?url=… (full URL lives in Actions JSON).
    # Env REMOTE_UI_HOST_ALLOWLIST=127.0.0.1,localhost,lyrics.example.com
    # Empty env → defaults (local mini services). Not a URL map — only hosts/IPs.
    REMOTE_UI_HOST_ALLOWLIST: List[str] = _parse_host_allowlist(
        os.getenv("REMOTE_UI_HOST_ALLOWLIST", ""),
        defaults=["127.0.0.1", "localhost"],
    )
    REMOTE_UI_TIMEOUT_SEC: float = float(os.getenv("REMOTE_UI_TIMEOUT_SEC", "12"))
    REMOTE_UI_MAX_BYTES: int = int(os.getenv("REMOTE_UI_MAX_BYTES", str(512 * 1024)))
    # Allowed URL schemes for proxied remote UI (http for LAN/Tailscale, https for public).
    REMOTE_UI_ALLOWED_SCHEMES: List[str] = [
        s.strip().lower()
        for s in os.getenv("REMOTE_UI_ALLOWED_SCHEMES", "http,https").split(",")
        if s.strip()
    ]

    # APNs (push о готовом ответе в чате KB App)
    APNS_KEY_ID: str = os.getenv("APNS_KEY_ID", "")
    APNS_TEAM_ID: str = os.getenv("APNS_TEAM_ID", "66C9VGAZR5")
    APNS_AUTH_KEY_PATH: Optional[str] = os.getenv("APNS_AUTH_KEY_PATH")
    APNS_TOPIC: str = os.getenv("APNS_TOPIC", "com.coredan.KnowledgeBaseApp")
    APNS_USE_SANDBOX: bool = os.getenv("APNS_USE_SANDBOX", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    
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

