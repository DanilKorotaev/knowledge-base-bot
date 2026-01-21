# Система ограничения доступа к папкам базы знаний

**Статус**: 📋 Запланировано  
**Приоритет**: 🟡 Средний  
**Категория**: Безопасность, Функциональность

## Описание

Реализация системы ограничения доступа пользователей к определенным папкам в базе знаний. Пользователи могут иметь доступ только к указанным папкам, и AI-ассистент (Cursor CLI) будет работать только с файлами из этих папок.

## Проблема

В текущей реализации пользователи либо имеют полный доступ ко всей базе знаний, либо не имеют доступа вообще. Для более гибкого управления доступом необходимо иметь возможность ограничивать пользователей определенными папками.

## Цели

1. Реализовать систему назначения папок пользователям
2. Реализовать фильтрацию файлов при работе с Cursor CLI на основе разрешенных папок
3. Реализовать административные команды для управления доступом к папкам
4. Реализовать проверку доступа к файлам перед их чтением/изменением
5. Реализовать логирование попыток доступа к запрещенным папкам
6. **Реализовать автоматическое создание NextCloud share links для папок с доступом только на чтение**
7. **Предоставлять пользователям ссылки на папки в NextCloud для прямого доступа через веб-интерфейс**

## Задачи

### База данных

- [ ] Добавить таблицу `user_folders` для связи пользователей и папок
- [ ] Добавить поле `nextcloud_share_id` в таблицу `user_folders` для хранения ID share в NextCloud
- [ ] Добавить поле `nextcloud_share_url` в таблицу `user_folders` для хранения ссылки на share
- [ ] Добавить поле `nextcloud_share_password` в таблицу `user_folders` для хранения пароля share (опционально, зашифровано)
- [ ] Добавить поле `share_expires_at` в таблицу `user_folders` для хранения даты истечения share (опционально)
- [ ] Реализовать миграцию БД для существующих пользователей

### Интерфейс базы данных

- [ ] Добавить метод `get_user_allowed_folders(user_id: int) -> List[str]` в `DatabaseInterface`
- [ ] Добавить метод `set_user_allowed_folders(user_id: int, folders: List[str]) -> None` в `DatabaseInterface`
- [ ] Добавить метод `add_user_folder(user_id: int, folder_path: str) -> None` в `DatabaseInterface`
- [ ] Добавить метод `remove_user_folder(user_id: int, folder_path: str) -> None` в `DatabaseInterface`
- [ ] Реализовать все методы в `PostgreSQLDatabase`
- [ ] Реализовать все методы в `SQLiteDatabase`

### Проверка доступа к файлам

- [ ] Создать утилиту `utils/access_control.py` для проверки доступа к файлам
- [ ] Реализовать функцию `is_file_accessible(user_id: int, file_path: str) -> bool`
- [ ] Реализовать функцию `filter_accessible_files(user_id: int, file_paths: List[str]) -> List[str]`
- [ ] Интегрировать проверку доступа в `services/cursor_cli_service.py`

### Фильтрация контекста для Cursor CLI

- [ ] Модифицировать `utils/context.py` для фильтрации файлов по разрешенным папкам
- [ ] Реализовать фильтрацию файлов при построении контекста для запросов
- [ ] Реализовать проверку доступа перед чтением/изменением файлов

### Административные команды

- [ ] Добавить в админское меню раздел управления доступом к папкам
- [ ] Реализовать команду для просмотра разрешенных папок пользователя
- [ ] Реализовать команду для добавления папки пользователю
- [ ] Реализовать команду для удаления папки у пользователя
- [ ] Реализовать команду для установки списка папок пользователю
- [ ] Реализовать интерактивный выбор папок из структуры базы знаний

### NextCloud Sharing Integration

- [ ] Расширить `services/nextcloud_service.py` методами для работы с Sharing API
- [ ] Реализовать метод `create_share_link(folder_path: str, password: Optional[str] = None, expire_date: Optional[datetime] = None) -> Dict[str, Any]`
- [ ] Реализовать метод `update_share_link(share_id: int, password: Optional[str] = None, expire_date: Optional[datetime] = None) -> bool`
- [ ] Реализовать метод `delete_share_link(share_id: int) -> bool`
- [ ] Реализовать метод `get_share_info(share_id: int) -> Optional[Dict[str, Any]]`
- [ ] Реализовать автоматическое создание share link при назначении папки пользователю
- [ ] Реализовать автоматическое удаление share link при удалении доступа к папке
- [ ] Реализовать генерацию безопасных паролей для share links (опционально)
- [ ] Реализовать отправку ссылки на папку пользователю через бота при назначении доступа
- [ ] Реализовать команду для повторной отправки ссылки пользователю
- [ ] Реализовать обновление share link при изменении настроек доступа

### Логирование и безопасность

- [ ] Реализовать логирование попыток доступа к запрещенным папкам
- [ ] Реализовать предупреждения администраторам о попытках доступа
- [ ] Реализовать валидацию путей к папкам (защита от path traversal)
- [ ] Реализовать шифрование паролей share links в БД
- [ ] Реализовать автоматическое обновление share links при изменении структуры папок

## Технические детали

### Структура таблицы user_folders

```sql
CREATE TABLE user_folders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    folder_path VARCHAR(500) NOT NULL,
    nextcloud_share_id INTEGER,  -- ID share в NextCloud
    nextcloud_share_url VARCHAR(500),  -- URL для доступа к share
    nextcloud_share_password VARCHAR(255),  -- Зашифрованный пароль (опционально)
    share_expires_at TIMESTAMP,  -- Дата истечения share (опционально)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, folder_path)
);
```

### NextCloud Sharing API

NextCloud предоставляет Sharing API для создания публичных ссылок на файлы и папки:

**Endpoint:** `POST /ocs/v2.php/apps/files_sharing/api/v1/shares`

**Параметры:**
- `path` - путь к папке/файлу в NextCloud
- `shareType` - тип share (3 для public link)
- `permissions` - права доступа (1 для read-only, 2 для read-write)
- `password` - пароль для доступа (опционально)
- `expireDate` - дата истечения в формате YYYY-MM-DD (опционально)

**Пример создания share link:**

```python
async def create_share_link(
    self,
    folder_path: str,
    password: Optional[str] = None,
    expire_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Создать share link для папки в NextCloud"""
    url = f"{self.url}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    auth = HTTPBasicAuth(self.username, self.password)
    
    # Получить полный путь к папке
    full_path = self._get_full_path(folder_path)
    
    params = {
        'path': full_path,
        'shareType': 3,  # Public link
        'permissions': 1,  # Read-only
    }
    
    if password:
        params['password'] = password
    
    if expire_date:
        params['expireDate'] = expire_date.strftime('%Y-%m-%d')
    
    headers = {
        'OCS-APIRequest': 'true',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    response = requests.post(url, auth=auth, data=params, headers=headers)
    response.raise_for_status()
    
    # Парсинг XML ответа
    root = ET.fromstring(response.text)
    share_data = {
        'id': int(root.find('.//id').text),
        'url': root.find('.//url').text,
        'token': root.find('.//token').text,
    }
    
    return share_data
```

**Управление share links:**

- Обновление: `PUT /ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}`
- Удаление: `DELETE /ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}`
- Получение информации: `GET /ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}`

### Пример проверки доступа

```python
def is_file_accessible(user_id: int, file_path: str) -> bool:
    """Проверить, доступен ли файл пользователю"""
    db = await get_db()
    allowed_folders = await db.get_user_allowed_folders(user_id)
    
    # Если список пуст - полный доступ
    if not allowed_folders:
        return True
    
    # Проверить, находится ли файл в одной из разрешенных папок
    for folder in allowed_folders:
        if file_path.startswith(folder):
            return True
    
    return False
```

### Интеграция с Cursor CLI

При построении контекста для Cursor CLI необходимо:
1. Получить список разрешенных папок пользователя
2. Отфильтровать файлы из контекста, которые не находятся в разрешенных папках
3. При чтении/изменении файла проверять доступ перед выполнением операции

### Интеграция с NextCloud Sharing

**Процесс назначения доступа к папке:**

1. Администратор назначает папку пользователю через админское меню
2. Система автоматически создает share link в NextCloud для этой папки:
   - Права доступа: только чтение (`permissions: 1`)
   - Опционально: пароль для дополнительной защиты
   - Опционально: дата истечения доступа
3. Информация о share сохраняется в БД (`user_folders` таблица)
4. Пользователю отправляется сообщение с ссылкой на папку в NextCloud:
   ```
   ✅ Вам предоставлен доступ к папке: {folder_path}
   
   📁 Открыть папку в NextCloud:
   {share_url}
   
   🔑 Пароль для доступа: {password} (если установлен)
   ```

**Управление share links:**

- При удалении доступа к папке → автоматически удаляется share link в NextCloud
- При изменении настроек доступа → обновляется share link (пароль, дата истечения)
- При запросе пользователя → можно повторно отправить ссылку

**Безопасность:**

- Share links создаются только с правами на чтение
- Пароли для share links опциональны, но рекомендуются для чувствительных данных
- Пароли хранятся в БД в зашифрованном виде
- Можно установить дату истечения доступа для временного доступа
- Пользователи, не зарегистрированные в NextCloud, могут получить доступ только через share link

## Связанные файлы

- `database/base.py` - интерфейс методов для работы с папками
- `database/postgresql_db.py` - реализация для PostgreSQL
- `database/sqlite_db.py` - реализация для SQLite
- `utils/access_control.py` - утилиты для проверки доступа (новый файл)
- `utils/context.py` - фильтрация контекста
- `services/cursor_cli_service.py` - интеграция проверки доступа
- `services/nextcloud_service.py` - расширение для работы с Sharing API
- `handlers/callbacks.py` - административные команды
- `handlers/keyboards.py` - клавиатуры для выбора папок
- `handlers/messages.py` - отправка ссылок пользователям

## Безопасность

1. **Валидация путей**: Проверка на path traversal атаки (`../`, `..\\`)
2. **Нормализация путей**: Приведение путей к единому формату
3. **Логирование**: Все попытки доступа к запрещенным папкам должны логироваться
4. **По умолчанию закрыто**: Если у пользователя нет разрешенных папок, он не имеет доступа (или полный доступ - настраиваемо)

## Примечания

- Эта задача расширяет функциональность системы ограничения доступа
- Можно реализовать как отдельную таблицу, так и JSON поле в таблице users
- Необходимо продумать интерфейс выбора папок для администраторов (обход файловой системы или предустановленный список)

### NextCloud Sharing - Особенности

1. **Пользователи без аккаунта NextCloud:**
   - Share links позволяют предоставить доступ пользователям, не зарегистрированным в NextCloud
   - Доступ предоставляется только через публичную ссылку с паролем (опционально)
   - Пользователь может просматривать содержимое папки через веб-интерфейс NextCloud

2. **Ограничение доступа:**
   - Share link предоставляет доступ только к указанной папке и всем вложенным файлам/папкам
   - Доступ к остальным папкам базы знаний отсутствует
   - Права доступа: только чтение (изменение файлов через share link невозможно)

3. **Управление доступом:**
   - Администратор может в любой момент отозвать доступ, удалив share link
   - Можно установить дату истечения доступа для временного доступа
   - Можно изменить пароль share link без удаления доступа

4. **Интеграция с ботом:**
   - При назначении доступа к папке пользователь автоматически получает ссылку через бота
   - Пользователь может запросить повторную отправку ссылки
   - Администратор видит список всех активных share links в админском меню

