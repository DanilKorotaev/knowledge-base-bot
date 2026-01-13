"""
Утилиты для работы с базой данных
"""
import logging
from typing import Optional
from database import DatabaseInterface, PostgreSQLDatabase, SQLiteDatabase
from config import config

logger = logging.getLogger(__name__)

# Глобальный экземпляр БД
_db_instance: Optional[DatabaseInterface] = None


async def get_db() -> DatabaseInterface:
    """Получить экземпляр базы данных (singleton)"""
    global _db_instance
    
    if _db_instance is None:
        if config.DB_TYPE == "postgresql":
            _db_instance = PostgreSQLDatabase()
            await _db_instance.connect()
        else:
            _db_instance = SQLiteDatabase()
        
        # Инициализировать БД (создать таблицы)
        await _db_instance.init_db()
        logger.info(f"База данных инициализирована ({config.DB_TYPE})")
    
    return _db_instance


async def close_db() -> None:
    """Закрыть соединение с базой данных"""
    global _db_instance
    
    if _db_instance:
        if hasattr(_db_instance, 'close'):
            await _db_instance.close()
        _db_instance = None
        logger.info("Соединение с базой данных закрыто")

