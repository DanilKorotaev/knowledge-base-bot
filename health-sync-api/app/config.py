import os
from pathlib import Path


class Settings:
    """Переменные окружения (см. docker-compose и .env)."""

    kb_path: Path = Path(os.getenv("HEALTH_SYNC_KB_PATH", "/var/knowledge-base-bot/kb"))
    api_token: str = os.getenv("HEALTH_SYNC_API_TOKEN", "").strip()
    workouts_subdir: str = "HealthData/workouts"
    daily_subdir: str = "HealthData/daily"
    training_root: str = "Тренировки"


settings = Settings()
