"""
Помощники для работы с файлами
"""
import hashlib
import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths whose body must never be stored/served as text in file_changes / chat API.
_BINARY_SUFFIXES = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".heic",
        ".heif",
        ".bmp",
        ".tif",
        ".tiff",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".7z",
        ".rar",
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".wav",
        ".flac",
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".dmg",
        ".ipa",
        ".apk",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".dat",
        ".sqlite",
        ".db",
        ".wasm",
    }
)

# Safety cap for text diffs exposed via related_changed_files.
FILE_CHANGE_TEXT_MAX_CHARS = 100_000


def is_binary_kb_path(path: str | Path | None) -> bool:
    """True for images/media/archives — not meaningful as UTF-8 chat diffs."""
    if path is None:
        return False
    suffix = Path(str(path)).suffix.lower()
    if suffix in _BINARY_SUFFIXES:
        return True
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        return False
    return not (
        mime.startswith("text/")
        or mime in {"application/json", "application/xml", "application/javascript"}
        or mime.endswith("+json")
        or mime.endswith("+xml")
    )


def looks_like_binary_blob(text: str | None) -> bool:
    """Heuristic for already-stored garbage from read_text(..., errors='ignore') on JPEGs."""
    if not text:
        return False
    if "\x00" in text:
        return True
    # Large mostly-non-printable payloads (legacy binary-as-text rows).
    if len(text) < 512:
        return False
    sample = text[:4000]
    weird = sum(1 for ch in sample if ord(ch) < 9 or (14 <= ord(ch) < 32))
    return (weird / len(sample)) > 0.08


def sanitize_file_change_text(path: str | Path | None, content: str | None) -> str | None:
    """Drop binary / oversized bodies before DB write or API serialize."""
    if content is None:
        return None
    if is_binary_kb_path(path) or looks_like_binary_blob(content):
        return None
    if len(content) > FILE_CHANGE_TEXT_MAX_CHARS:
        return content[:FILE_CHANGE_TEXT_MAX_CHARS]
    return content


def read_text_for_file_change(file_path: Path) -> Optional[str]:
    """Read file body for file_changes only when it is plausible text."""
    if is_binary_kb_path(file_path):
        return None
    try:
        # Reject obvious binary via NUL in the first chunk.
        with file_path.open("rb") as fh:
            head = fh.read(8192)
        if b"\x00" in head:
            return None
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return sanitize_file_change_text(file_path, text)


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
        try:
            from utils.health_linking_hook import maybe_link_health_after_training_note_saved

            maybe_link_health_after_training_note_saved(file_path)
        except Exception:
            logger.debug("Health link hook after write_file_content skipped", exc_info=True)
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
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Получить информацию о файле
        logger.debug(f"Получаю информацию о файле {file_id} из Telegram")
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
        
        logger.debug(f"Скачиваю файл {file_id} в {save_path}")
        # Скачать файл
        await bot.download_file(file.file_path, destination=save_path)
        
        if save_path.exists():
            file_size = save_path.stat().st_size
            logger.info(f"Файл {file_id} успешно скачан: {save_path} ({file_size} байт)")
        else:
            logger.warning(f"Файл скачан, но не найден по пути: {save_path}")
        
        return save_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла {file_id}: {e}", exc_info=True)
        return None

