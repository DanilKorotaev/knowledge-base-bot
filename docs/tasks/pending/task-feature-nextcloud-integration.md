# Интеграция с NextCloud

**Статус**: 🚧 В процессе  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация интеграции с NextCloud через WebDAV API для синхронизации локальной копии базы знаний с NextCloud.

## Цели

1. ✅ Реализовать аутентификацию в NextCloud через WebDAV
2. ✅ Реализовать загрузку/скачивание файлов
3. ✅ Реализовать синхронизацию директорий
4. ❌ Реализовать обнаружение конфликтов

## Задачи

- [x] Создать NextCloudService
- [x] Реализовать аутентификацию через WebDAV
- [x] Реализовать методы:
  - [x] `list_files(path)` - список файлов
  - [x] `read_file(path)` - чтение файла
  - [x] `write_file(path, content)` - запись файла
  - [x] `upload_file(local_path, remote_path)` - загрузка файла
  - [x] `download_file(remote_path, local_path)` - скачивание файла
  - [x] `sync_directory(local_path, remote_path)` - синхронизация (через sync_service)
- [ ] Реализовать обнаружение конфликтов
- [x] Реализовать обработку ошибок

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

