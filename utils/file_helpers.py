"""
Помощники для работы с файлами
"""
import hashlib
import tempfile
from pathlib import Path
from typing import Optional


def calculate_file_hash(file_path: Path) -> str:
    """Вычислить хеш файла"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def read_file_content(file_path: Path) -> Optional[str]:
    """Прочитать содержимое файла"""
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return None


def write_file_content(file_path: Path, content: str) -> bool:
    """Записать содержимое в файл"""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


async def download_telegram_file(bot, file_id: str, file_path: Optional[str] = None) -> Optional[Path]:
    """
    Скачать файл из Telegram
    
    Args:
        bot: Экземпляр Telegram бота
        file_id: ID файла в Telegram
        file_path: Опциональный путь для сохранения файла
    
    Returns:
        Path к скачанному файлу или None в случае ошибки
    """
    try:
        # Получить информацию о файле
        file = await bot.get_file(file_id)
        
        # Определить путь для сохранения
        if file_path:
            save_path = Path(file_path)
        else:
            # Использовать временную директорию
            temp_dir = Path(tempfile.gettempdir()) / "knowledge_base_bot"
            temp_dir.mkdir(parents=True, exist_ok=True)
            # Использовать file_id как имя файла, сохраняя расширение
            file_extension = Path(file.file_path).suffix if file.file_path else ".ogg"
            save_path = temp_dir / f"{file_id}{file_extension}"
        
        # Скачать файл
        await bot.download_file(file.file_path, destination=save_path)
        
        return save_path
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при скачивании файла {file_id}: {e}", exc_info=True)
        return None

