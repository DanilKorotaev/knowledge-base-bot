# Отслеживание изменений файлов

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация системы отслеживания изменений файлов в базе знаний с возможностью отката изменений.

## Цели

1. Реализовать отслеживание изменений файлов (создание, изменение, удаление)
2. Реализовать сохранение истории изменений в БД
3. Реализовать откат конкретного изменения
4. Реализовать откат всех изменений сессии
5. Реализовать валидацию изменений (проверка хешей)

## Задачи

- [ ] Создать `services/change_tracker.py`
- [ ] Реализовать метод `track_file_change()` - отслеживание изменения
- [ ] Реализовать метод `get_file_history()` - получение истории изменений файла
- [ ] Реализовать метод `revert_change()` - откат конкретного изменения
- [ ] Реализовать метод `revert_session_changes()` - откат всех изменений сессии
- [ ] Реализовать метод `save_file_states()` - сохранение состояния файлов перед изменениями
- [ ] Реализовать интеграцию с БД для сохранения истории
- [ ] Реализовать валидацию изменений (проверка хешей)
- [ ] Реализовать сравнение файлов (до/после)

## Технические детали

### Структура изменений

```python
{
    "id": 1,
    "session_id": 123,
    "file_path": "/path/to/file.md",
    "change_type": "modified",  # 'created', 'modified', 'deleted'
    "old_content": "...",
    "new_content": "...",
    "file_hash": "sha256_hash",
    "created_at": "2025-01-07T12:00:00Z"
}
```

### Пример реализации

```python
# В services/change_tracker.py
from utils.file_helpers import calculate_file_hash, read_file_content, write_file_content

class ChangeTracker:
    async def track_file_change(
        self,
        session_id: int,
        file_path: str,
        change_type: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None
    ):
        """Отследить изменение файла"""
        file_hash = None
        if new_content:
            file_hash = hashlib.sha256(new_content.encode()).hexdigest()
        
        return await self.db.log_file_change(
            session_id=session_id,
            file_path=file_path,
            change_type=change_type,
            old_content=old_content,
            new_content=new_content,
            file_hash=file_hash
        )
    
    async def revert_change(self, change_id: int) -> bool:
        """Откатить конкретное изменение"""
        change = await self.db.get_file_change(change_id)
        if not change:
            return False
        
        file_path = Path(change["file_path"])
        
        if change["change_type"] == "created":
            # Удалить файл
            file_path.unlink()
        elif change["change_type"] == "deleted":
            # Восстановить файл
            write_file_content(file_path, change["old_content"])
        elif change["change_type"] == "modified":
            # Восстановить старое содержимое
            write_file_content(file_path, change["old_content"])
        
        return True
```

## Связанные файлы

- `services/change_tracker.py` - основной сервис
- `database/base.py` - методы для работы с БД
- `utils/file_helpers.py` - помощники для работы с файлами
- `handlers/commands.py` - команды `/history`, `/revert`

