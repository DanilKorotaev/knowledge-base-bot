# Задача: Прямые ссылки на файлы в NextCloud Web UI

**Статус**: ✅ Выполнено  
**Приоритет**: 🟡 Средний  
**Категория**: Новые функции

## Описание

При изменении файлов через Cursor CLI пользователь видит только пути, но не может перейти к файлу — приходится искать вручную в NextCloud. Нужно генерировать кликабельные ссылки на веб-интерфейс NextCloud для каждого изменённого файла.

## Проблема

Сейчас сообщение об изменениях выглядит так:
```
📝 Изменено файлов: 2
  • Документы/Тачки/Заправки/AЗС/TEBOIL М-2 Всходы.md
  • Документы/Тачки/Соляра/Расходы/Топливо/2026-02-08 Заправка.md
✅ Изменения синхронизированы с NextCloud
```

Пути не ведут никуда. Пользователю нужно вручную открывать NextCloud и искать файл.

## Проблема авторизации

**Важно:** прямые ссылки вида `/f/{fileid}` или `/apps/files/?dir=...` требуют авторизации в NextCloud. При нажатии в Telegram ссылка откроется во встроенном in-app браузере, где нет сессии NextCloud → пользователь увидит страницу логина.

### Варианты решения проблемы авторизации

| Вариант | Плюсы | Минусы |
|---------|-------|--------|
| **A. Share-ссылки (OCS API)** | Не требуют авторизации; открываются сразу | Нужна очистка; доп. API-запрос; вопрос безопасности |
| **B. Direct-ссылки + inline-кнопки** | Простая реализация | В in-app браузере нужен логин; пользователь может выбрать "Открыть в браузере" |
| **C. Share-ссылки + expiration** (рекомендуемый) | Работают без авторизации; безопасно с коротким сроком | Нужна реализация OCS Share API |
| **D. Mini App** | Лучший UX; авторизация не нужна | Отдельная задача, требует хостинг |

### Рекомендуемый подход: Share-ссылки с expiration (Вариант C)

NextCloud OCS Share API позволяет создавать публичные ссылки:
```
POST /ocs/v2.php/apps/files_sharing/api/v1/shares
```

Параметры:
- `path` — путь к файлу
- `shareType=3` — public link
- `permissions=1` — read-only
- `expireDate` — срок жизни (например, 24 часа)

Ссылка будет вида: `https://cloud.example.com/s/AbCdEfGh12345` — открывается без авторизации, с ограниченным сроком.

## Решение

Генерировать **публичные share-ссылки** через OCS Share API с коротким сроком жизни. С fallback на прямые ссылки, если share API недоступен.

## Задачи

### 1. Конфигурация

- [x] Добавить переменные в `config.py`:
  ```python
  NEXTCLOUD_WEB_URL: Optional[str] = os.getenv("NEXTCLOUD_WEB_URL")  # fallback на NEXTCLOUD_URL
  NEXTCLOUD_LINK_MODE: str = os.getenv("NEXTCLOUD_LINK_MODE", "share")  # "share" | "direct" | "disabled"
  NEXTCLOUD_SHARE_EXPIRATION_HOURS: int = int(os.getenv("NEXTCLOUD_SHARE_EXPIRATION_HOURS", "24"))
  ```

### 2. OCS Share API в NextCloudService

- [x] Добавить метод `create_share_link()` в `NextCloudService`:
  ```python
  async def create_share_link(self, remote_path: str, expire_hours: int = 24) -> Optional[str]:
      """Создать публичную share-ссылку через OCS Share API"""
  ```
  - `POST /ocs/v2.php/apps/files_sharing/api/v1/shares`
  - `shareType=3` (public link), `permissions=1` (read-only)
  - `expireDate` = текущая дата + `expire_hours`
  - Вернуть URL публичной ссылки из ответа (`url` поле)
  - Header: `OCS-APIREQUEST: true`, `Accept: application/json`

- [x] Добавить метод `delete_share()` — для очистки (опционально):
  ```python
  async def delete_share(self, share_id: int) -> bool:
      """Удалить share-ссылку"""
  ```

### 3. Получение file ID через PROPFIND (для fallback на direct-ссылки)

- [x] Добавить метод `get_file_id()` в `NextCloudService`:
  ```python
  async def get_file_id(self, remote_path: str) -> Optional[int]:
      """Получить file ID через PROPFIND с oc:fileid"""
  ```
  - PROPFIND запрос с namespace `xmlns:oc="http://owncloud.org/ns"` и свойством `<oc:fileid/>`
  - Парсинг XML-ответа для извлечения числового ID

### 4. Генерация URL (с учётом режима)

- [x] Добавить метод `get_file_link()` в `NextCloudService`:
  ```python
  async def get_file_link(self, remote_path: str) -> Optional[str]:
      """Получить ссылку на файл в зависимости от настроенного режима"""
  ```
  - Если `NEXTCLOUD_LINK_MODE == "share"` → `create_share_link()`
  - Если `NEXTCLOUD_LINK_MODE == "direct"` → `get_web_url()` (прямая ссылка /f/{id})
  - Если `NEXTCLOUD_LINK_MODE == "disabled"` → `None`
  - Fallback: если share не удалось → direct, если direct не удалось → None

- [x] Добавить метод `get_web_url()` (для режима direct):
  ```python
  def get_web_url(self, remote_path: str, file_id: Optional[int] = None) -> str:
      """Сконструировать прямую ссылку на веб-интерфейс NextCloud"""
  ```
  - Если `file_id` есть → `{web_url}/f/{file_id}`
  - Если нет → `{web_url}/apps/files/?dir={parent_dir}&scrollto={filename}`

### 5. Расширение PROPFIND (для direct-режима)

- [x] Расширить `_parse_propfind_response()` — парсить `oc:fileid` при наличии в ответе
- [x] Добавить `oc:fileid` в PROPFIND запрос `list_files()`:
  ```xml
  <d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
      <d:prop>
          <d:getlastmodified/>
          <d:getcontentlength/>
          <d:resourcetype/>
          <oc:fileid/>
      </d:prop>
  </d:propfind>
  ```

### 6. Обновление формата сообщений

- [x] Изменить `format_file_changes_info()` в `utils/message_helpers.py`:
  - Добавить параметр `file_urls: Optional[Dict[str, str]]` (словарь путь → URL)
  - Формировать HTML-ссылку: `<a href="{url}">📎 Открыть</a>` рядом с путём
  - Если URL недоступен — показывать только путь в `<code>`
  - Для 1-2 файлов: inline-кнопки (InlineKeyboardButton с url) — удобнее на мобильных
- [x] Обновить `handle_file_changes()` в `QueryProcessingService`:
  - Получать ссылки для каждого изменённого файла через `get_file_link()`
  - Передавать в `format_file_changes_info()`

## Пример результата

### Режим share (рекомендуемый)

```
📝 Изменено файлов: 2
  • TEBOIL М-2 Всходы.md  📎 Открыть     ← share-ссылка, работает без авторизации
  • 2026-02-08 Заправка.md  📎 Открыть
✅ Изменения синхронизированы с NextCloud
```

Где "📎 Открыть" — `<a href="https://cloud.example.com/s/AbCdEfGh">📎 Открыть</a>`.

### Для 1-2 файлов — inline-кнопки

```
📝 Изменено файлов: 1
  • TEBOIL М-2 Всходы.md
✅ Изменения синхронизированы с NextCloud

[📎 Открыть TEBOIL М-2 Всходы.md]   ← InlineKeyboardButton(url=...)
```

### Режим direct (fallback)

```
📝 Изменено файлов: 2
  • TEBOIL М-2 Всходы.md  🔗 Открыть     ← требует авторизации!
  • 2026-02-08 Заправка.md  🔗 Открыть
⚠️ Ссылки требуют авторизации в NextCloud
```

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|------------|-----------|
| **Ссылка открывается в in-app браузере без авторизации** | Высокая (для direct) | Использовать share-ссылки (режим по умолчанию) |
| OCS Share API недоступен или отключен | Низкая | Fallback на direct-ссылки с предупреждением |
| Накопление старых share-ссылок | Средняя | `expireDate` — NextCloud автоматически удаляет просроченные |
| NextCloud PROPFIND не возвращает `oc:fileid` | Низкая | Fallback на URL с `dir` + `scrollto` |
| Дополнительные HTTP-запросы замедляют ответ | Средняя | Share-ссылки создаются параллельно; кэшировать `fileid` |
| `NEXTCLOUD_WEB_URL` не настроен | Низкая | Fallback на `NEXTCLOUD_URL` |
| Безопасность: share-ссылки доступны без авторизации | Низкая | Read-only + expiration 24ч; можно добавить пароль |

## Оценка

- **Сложность**: 🟡 Средняя
- **Время**: ~3-4 часа

## Связанные файлы

- `config.py` — переменные `NEXTCLOUD_WEB_URL`, `NEXTCLOUD_LINK_MODE`, `NEXTCLOUD_SHARE_EXPIRATION_HOURS`
- `services/nextcloud_service.py` — методы `create_share_link()`, `get_file_id()`, `get_web_url()`, `get_file_link()`
- `utils/message_helpers.py` — обновление `format_file_changes_info()`
- `services/query_processing_service.py` — передача URL в форматирование

## Связанные задачи

- [Исправить отображение путей к файлам в Telegram](task-ux-fix-file-paths-in-telegram.md) — предварительный фикс (делать первым)
- [Mini App для управления сессиями](task-feature-miniapp-sessions.md) — в будущем можно просматривать файлы прямо в Telegram (Этап 4) — решает проблему авторизации полностью
