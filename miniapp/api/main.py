"""
FastAPI приложение для Mini App
"""
import logging
import os
import sys

# Добавляем корень проекта в sys.path для импорта config, database и т.д.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .routes import router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="Knowledge Base Bot - Mini App API",
    description="API для Telegram Mini App управления сессиями",
    version="1.0.0"
)

# Настройка CORS
# MINIAPP_CORS_ORIGINS — список доменов через запятую (по умолчанию * для разработки)
cors_origins_env = os.getenv("MINIAPP_CORS_ORIGINS", "*")
if cors_origins_env == "*":
    cors_origins = ["*"]
else:
    cors_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем API маршруты
app.include_router(router)

# Путь к статическим файлам
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


@app.get("/")
async def serve_index():
    """Отдать главную HTML-страницу Mini App"""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"error": "index.html not found"}


# Монтируем статические файлы
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Mini App API запущен")
    
    # Инициализация БД
    from utils.db_helpers import get_db
    await get_db()
    logger.info("База данных инициализирована для Mini App")


@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при остановке"""
    logger.info("Mini App API остановлен")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("MINIAPP_PORT", "8080"))
    host = os.getenv("MINIAPP_HOST", "0.0.0.0")
    
    uvicorn.run(
        "miniapp.api.main:app",
        host=host,
        port=port,
        reload=True
    )

