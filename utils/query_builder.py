"""
Утилиты для сборки запросов из множественных сообщений
"""
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class QueryBuilder:
    """Класс для сборки финального запроса из множественных сообщений"""
    
    def __init__(self):
        self.text_parts: List[str] = []
        self.voice_files: List[Dict[str, Any]] = []  # {file_id, file_path, transcription}
        self.media_files: List[Dict[str, Any]] = []  # {file_id, file_path, file_name, file_type}
    
    def add_text(self, text: str):
        """Добавить текстовую часть"""
        if text and text.strip():
            self.text_parts.append(text.strip())
    
    def add_voice(self, file_id: str, file_path: Optional[Path] = None, transcription: Optional[str] = None):
        """Добавить голосовое сообщение"""
        self.voice_files.append({
            "file_id": file_id,
            "file_path": file_path,
            "transcription": transcription
        })
    
    def add_media(self, file_id: str, file_path: Path, file_name: str, file_type: str):
        """Добавить медиа файл (фото, документ)"""
        self.media_files.append({
            "file_id": file_id,
            "file_path": file_path,
            "file_name": file_name,
            "file_type": file_type
        })
    
    def build_query(self) -> str:
        """
        Собрать финальный запрос из всех компонентов
        
        Returns:
            str: Собранный запрос для отправки в Cursor CLI
        """
        parts = []
        
        # Добавить текстовые части
        if self.text_parts:
            parts.extend(self.text_parts)
        
        # Добавить расшифровки голосовых сообщений
        for voice in self.voice_files:
            if voice.get("transcription"):
                parts.append(f"[Голосовое сообщение: {voice['transcription']}]")
        
        # Добавить информацию о медиа файлах
        if self.media_files:
            media_info = []
            for media in self.media_files:
                file_name = media.get("file_name", "файл")
                file_type = media.get("file_type", "файл")
                file_path = media.get("file_path")
                
                if file_path:
                    # Преобразовать абсолютный путь в относительный от корня базы знаний
                    file_path_obj = Path(file_path) if isinstance(file_path, str) else file_path
                    try:
                        from config import config
                        kb_path = config.LOCAL_KB_PATH
                        # Проверка, что путь находится внутри базы знаний
                        try:
                            relative_path = file_path_obj.relative_to(kb_path)
                            media_info.append(f"- {file_type}: {file_name} (путь: {relative_path})")
                        except ValueError:
                            # Путь не находится внутри базы знаний
                            media_info.append(f"- {file_type}: {file_name} (путь: {file_path_obj})")
                    except Exception:
                        # Если не удалось вычислить относительный путь, используем как есть
                        media_info.append(f"- {file_type}: {file_name} (путь: {file_path_obj})")
                else:
                    media_info.append(f"- {file_type}: {file_name}")
            
            if media_info:
                parts.append("\n[Прикрепленные файлы:]")
                parts.append("\n".join(media_info))
        
        return "\n\n".join(parts) if parts else ""
    
    def get_summary(self) -> str:
        """Получить краткое описание собранных компонентов"""
        summary_parts = []
        
        if self.text_parts:
            summary_parts.append(f"📝 Текстовых сообщений: {len(self.text_parts)}")
        
        if self.voice_files:
            summary_parts.append(f"🎤 Голосовых сообщений: {len(self.voice_files)}")
        
        if self.media_files:
            summary_parts.append(f"📎 Файлов: {len(self.media_files)}")
        
        return "\n".join(summary_parts) if summary_parts else "Пусто"
    
    def has_content(self) -> bool:
        """Проверить, есть ли какой-либо контент"""
        return bool(self.text_parts or self.voice_files or self.media_files)
    
    def clear(self):
        """Очистить все собранные данные"""
        self.text_parts.clear()
        self.voice_files.clear()
        self.media_files.clear()


def query_builder_from_state(state_data: Dict[str, Any]) -> QueryBuilder:
    """Создать QueryBuilder из данных состояния FSM"""
    builder = QueryBuilder()
    
    # Восстановить текстовые части
    if "text_parts" in state_data:
        for text in state_data["text_parts"]:
            builder.add_text(text)
    
    # Восстановить голосовые сообщения
    if "voice_files" in state_data:
        for voice in state_data["voice_files"]:
            builder.add_voice(
                voice.get("file_id"),
                Path(voice["file_path"]) if voice.get("file_path") else None,
                voice.get("transcription")
            )
    
    # Восстановить медиа файлы
    if "media_files" in state_data:
        for media in state_data["media_files"]:
            builder.add_media(
                media.get("file_id"),
                Path(media["file_path"]) if media.get("file_path") else None,
                media.get("file_name", ""),
                media.get("file_type", "")
            )
    
    return builder


def query_builder_to_state(builder: QueryBuilder) -> Dict[str, Any]:
    """Преобразовать QueryBuilder в данные для сохранения в FSM"""
    state_data = {
        "text_parts": builder.text_parts.copy(),
        "voice_files": [
            {
                "file_id": v.get("file_id"),
                "file_path": str(v["file_path"]) if v.get("file_path") else None,
                "transcription": v.get("transcription")
            }
            for v in builder.voice_files
        ],
        "media_files": [
            {
                "file_id": m.get("file_id"),
                "file_path": str(m["file_path"]) if m.get("file_path") else None,
                "file_name": m.get("file_name", ""),
                "file_type": m.get("file_type", "")
            }
            for m in builder.media_files
        ]
    }
    return state_data

