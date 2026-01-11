# Интеграция с NextCloud

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация интеграции с NextCloud через WebDAV API для синхронизации локальной копии базы знаний с NextCloud.

## Цели

1. Реализовать аутентификацию в NextCloud через WebDAV
2. Реализовать загрузку/скачивание файлов
3. Реализовать синхронизацию директорий
4. Реализовать обнаружение конфликтов

## Задачи

- [ ] Создать NextCloudService
- [ ] Реализовать аутентификацию через WebDAV
- [ ] Реализовать методы:
  - `list_files(path)` - список файлов
  - `read_file(path)` - чтение файла
  - `write_file(path, content)` - запись файла
  - `upload_file(local_path, remote_path)` - загрузка файла
  - `download_file(remote_path, local_path)` - скачивание файла
  - `sync_directory(local_path, remote_path)` - синхронизация
- [ ] Реализовать обнаружение конфликтов
- [ ] Реализовать обработку ошибок

## Технические детали

### Использование библиотеки

```python
# Вариант 1: nextcloud-api-wrapper
from nextcloud_api_wrapper import NextCloud

# Вариант 2: requests с WebDAV
import requests
from requests.auth import HTTPBasicAuth
```

## Связанные файлы

- `services/nextcloud_service.py` - основной сервис
- `services/sync_service.py` - сервис синхронизации
- `config.py` - конфигурация NextCloud

