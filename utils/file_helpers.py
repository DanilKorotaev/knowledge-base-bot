"""
Помощники для работы с файлами
"""
import hashlib
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

