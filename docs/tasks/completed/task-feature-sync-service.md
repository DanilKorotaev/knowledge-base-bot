# Синхронизация с NextCloud

**Статус**: ✅ Выполнено  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация сервиса синхронизации локальной копии базы знаний с NextCloud через WebDAV API.

## Цели

1. ✅ Реализовать синхронизацию изменений в NextCloud
2. ✅ Реализовать синхронизацию изменений из NextCloud
3. ✅ Реализовать синхронизацию конкретного файла
4. ✅ Реализовать обнаружение конфликтов синхронизации
5. ✅ Реализовать периодическую синхронизацию
6. ✅ Реализовать синхронизацию после изменений бота

## Задачи

- [x] Создать `services/sync_service.py`
- [x] Реализовать метод `sync_to_nextcloud()` - синхронизация изменений в NextCloud
- [x] Реализовать метод `sync_from_nextcloud()` - синхронизация изменений из NextCloud
- [x] Реализовать метод `sync_file()` - синхронизация конкретного файла
- [x] Реализовать метод `sync_changes()` - синхронизация списка изменений
- [x] Реализовать метод `detect_conflicts()` - обнаружение конфликтов синхронизации
- [x] Реализовать периодическую синхронизацию (через asyncio)
- [x] Реализовать синхронизацию после изменений бота
- [x] Реализовать обработку ошибок синхронизации
- [x] Реализовать логирование операций синхронизации
- [x] Реализовать команду `/sync` - принудительная синхронизация с NextCloud
- [x] Реализовать уведомление пользователя о статусе синхронизации
- [x] Реализовать обработку конфликтов (разрешение вручную или автоматически) - метод `resolve_conflict()` с стратегиями "local", "remote"

## Технические детали

### Периодическая синхронизация

```python
# В sync_service.py
async def start_periodic_sync(self):
    """Запустить периодическую синхронизацию"""
    while True:
        await asyncio.sleep(config.SYNC_INTERVAL)
        try:
            await self.sync_from_nextcloud()
        except Exception as e:
            logger.error(f"Ошибка при синхронизации: {e}")
```

### Синхронизация после изменений

```python
# После изменений файлов через Cursor CLI
if changes:
    await sync_service.sync_to_nextcloud()
```

### Обнаружение конфликтов

```python
async def detect_conflicts(self, file_path: str) -> Optional[dict]:
    """Обнаружить конфликты синхронизации"""
    local_hash = calculate_file_hash(Path(file_path))
    remote_hash = await self.nextcloud_service.get_file_hash(file_path)
    
    if local_hash != remote_hash:
        return {
            "file_path": file_path,
            "local_hash": local_hash,
            "remote_hash": remote_hash,
            "conflict": True
        }
    return None
```

## Связанные файлы

- `services/sync_service.py` - основной сервис
- `services/nextcloud_service.py` - работа с NextCloud
- `services/change_tracker.py` - отслеживание изменений
- `config.py` - настройки синхронизации

