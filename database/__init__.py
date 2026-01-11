"""
Модуль для работы с базой данных
"""
from .base import DatabaseInterface
from .postgresql_db import PostgreSQLDatabase
from .sqlite_db import SQLiteDatabase

__all__ = ["DatabaseInterface", "PostgreSQLDatabase", "SQLiteDatabase"]

