# Telegram Mini App для управления сессиями

**Статус**: 📋 Запланировано  
**Приоритет**: 🔴 Высокий  
**Категория**: Новые функции

## Описание

Реализация Telegram Mini App для удобного управления сессиями чата. Mini App позволит пользователю просматривать список сессий, переключаться между ними, просматривать историю сообщений и управлять сессиями в удобном веб-интерфейсе.

## Цели

1. Создать Telegram Mini App для управления сессиями
2. Реализовать список сессий с фильтрацией и поиском
3. Реализовать просмотр истории сообщений сессии в форматированном виде
4. Реализовать переключение активной сессии из Mini App
5. Реализовать удаление и управление сессиями
6. Интегрировать Mini App с ботом через Web App API

## Задачи

### Структура Mini App

- [ ] Создать структуру папок для Mini App:
  ```
  miniapp/
  ├── static/
  │   ├── index.html
  │   ├── css/
  │   │   └── styles.css
  │   └── js/
  │       ├── app.js
  │       ├── telegram-api.js
  │       └── sessions.js
  ├── api/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── routes.py
  │   └── auth.py
  ├── Dockerfile
  └── README.md
  ```
- [ ] Создать базовый HTML с Telegram Web App API
- [ ] Создать стили для красивого отображения сессий и сообщений
- [ ] Создать JavaScript логику для работы с сессиями

### API для Mini App

- [ ] Реализовать REST API endpoints:
  - `GET /api/sessions` - получить список сессий пользователя
  - `GET /api/sessions/{session_id}` - получить детали сессии
  - `GET /api/sessions/{session_id}/messages` - получить сообщения сессии
  - `POST /api/sessions/{session_id}/switch` - переключиться на сессию
  - `DELETE /api/sessions/{session_id}` - удалить сессию
  - `POST /api/sessions/{session_id}/end` - завершить сессию
- [ ] Реализовать аутентификацию через Telegram Web App initData
- [ ] Реализовать валидацию пользователя и проверку прав доступа
- [ ] Реализовать обработку ошибок и возврат понятных сообщений

### Интерфейс списка сессий

- [ ] Реализовать отображение списка сессий:
  - ID сессии
  - Тип сессии (с контекстом БЗ / без контекста)
  - Статус (активна / завершена / отменена)
  - Количество сообщений
  - Дата создания
  - Индикатор активной сессии
- [ ] Реализовать фильтрацию по статусу
- [ ] Реализовать сортировку (по дате, по активности)
- [ ] Реализовать пагинацию для большого количества сессий
- [ ] Реализовать поиск по ID или содержимому

### Просмотр сессии

- [ ] Реализовать отображение истории сообщений:
  - Разделение сообщений пользователя и ассистента
  - Форматирование Markdown
  - Отображение времени сообщений
  - Отображение вложений (файлы, фото, голосовые)
- [ ] Реализовать красивую верстку диалога (как в чате)
- [ ] Реализовать прокрутку к последнему сообщению
- [ ] Реализовать копирование текста сообщений

### Управление сессиями

- [ ] Реализовать кнопку "Переключиться" для активации сессии
- [ ] Реализовать кнопку "Удалить" с подтверждением
- [ ] Реализовать кнопку "Завершить" для завершения активной сессии
- [ ] Реализовать кнопку "Вернуться в чат" для закрытия Mini App и перехода в чат бота
- [ ] Реализовать обновление списка после действий

### Интеграция с ботом

- [ ] Добавить inline-кнопку для открытия Mini App в главном меню
- [ ] Реализовать обработчик `handlers/webapp.py` для приема данных от Mini App
- [ ] Реализовать отправку уведомлений в чат при переключении сессии
- [ ] Реализовать обновление активной сессии в базе данных
- [ ] Реализовать синхронизацию состояния между Mini App и чатом

### Развертывание

- [ ] Создать Dockerfile для Mini App
- [ ] Настроить переменные окружения (MINIAPP_URL, API_URL)
- [ ] Настроить HTTPS для Web App (обязательно для Telegram)
- [ ] Создать документацию по развертыванию
- [ ] Настроить CORS для API

## Примеры интерфейса

### Список сессий

```
📋 Мои сессии

🟢 #123 - Активна
   📚 С контекстом БЗ
   💬 5 сообщений
   📅 15 янв 2024, 10:30
   [Переключиться] [Просмотреть] [Удалить]

⚪ #122 - Завершена
   💬 Без контекста
   💬 2 сообщения
   📅 14 янв 2024, 15:20
   [Переключиться] [Просмотреть] [Удалить]

[➕ Новая сессия] [🔄 Обновить]
```

### Просмотр сессии

```
📋 Сессия #123

🟢 Активна | 📚 С контекстом БЗ
Создана: 15 янв 2024, 10:30

─────────────────────────

👤 Вы
10:30
Найди информацию о системе авторасходов

─────────────────────────

🤖 Ассистент
10:31
Система авторасходов - это система для учета расходов на автомобиль...

─────────────────────────

👤 Вы
10:35
Обнови документацию

─────────────────────────

🤖 Ассистент
10:36
Документация обновлена. Изменены следующие файлы:
- Документация/Авторасходы/Авторасходы.md

[🔄 Переключиться] [⏹ Завершить] [🗑 Удалить] [💬 Вернуться в чат]
```

## Технические детали

### Структура API

```python
# В miniapp/api/routes.py

from fastapi import APIRouter, Depends, HTTPException
from .auth import verify_telegram_auth

router = APIRouter()

@router.get("/api/sessions")
async def get_sessions(user_id: int = Depends(verify_telegram_auth)):
    """Получить список сессий пользователя"""
    db = await get_db()
    user = await db.get_user_by_telegram_id(user_id)
    sessions = await db.get_user_sessions(user["id"])
    return {"sessions": sessions}

@router.get("/api/sessions/{session_id}")
async def get_session(
    session_id: int,
    user_id: int = Depends(verify_telegram_auth)
):
    """Получить детали сессии"""
    db = await get_db()
    session = await db.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    user = await db.get_user_by_telegram_id(user_id)
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Нет доступа к этой сессии")
    
    return session

@router.get("/api/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: int,
    user_id: int = Depends(verify_telegram_auth)
):
    """Получить сообщения сессии"""
    db = await get_db()
    # Проверка доступа...
    messages = await db.get_session_messages(session_id)
    return {"messages": messages}

@router.post("/api/sessions/{session_id}/switch")
async def switch_session(
    session_id: int,
    user_id: int = Depends(verify_telegram_auth)
):
    """Переключиться на сессию"""
    db = await get_db()
    # Проверка доступа...
    
    user = await db.get_user_by_telegram_id(user_id)
    active_session = await db.get_active_session(user["id"])
    if active_session:
        await db.update_session(active_session["id"], status="completed")
    
    await db.update_session(session_id, status="active")
    
    # Отправить уведомление в чат через бота
    from bot import bot
    await bot.send_message(
        user_id,
        f"✅ Переключено на сессию #{session_id}"
    )
    
    return {"success": True, "session_id": session_id}
```

### JavaScript для работы с API

```javascript
// В miniapp/static/js/sessions.js

class SessionsManager {
    constructor() {
        this.apiUrl = window.API_URL || '/api';
        this.telegram = window.Telegram?.WebApp;
    }
    
    async getSessions() {
        const initData = this.telegram?.initData;
        const response = await fetch(`${this.apiUrl}/sessions`, {
            headers: {
                'X-Telegram-Init-Data': initData
            }
        });
        return response.json();
    }
    
    async getSessionMessages(sessionId) {
        const initData = this.telegram?.initData;
        const response = await fetch(`${this.apiUrl}/sessions/${sessionId}/messages`, {
            headers: {
                'X-Telegram-Init-Data': initData
            }
        });
        return response.json();
    }
    
    async switchSession(sessionId) {
        const initData = this.telegram?.initData;
        const response = await fetch(`${this.apiUrl}/sessions/${sessionId}/switch`, {
            method: 'POST',
            headers: {
                'X-Telegram-Init-Data': initData,
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            // Закрыть Mini App и вернуться в чат
            this.telegram?.close();
        }
        
        return response.json();
    }
}
```

### Интеграция с ботом

```python
# В handlers/keyboards.py

def get_miniapp_inline_keyboard(web_app_url: str = None) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой Mini App для управления сессиями"""
    if web_app_url is None:
        web_app_url = os.getenv("MINIAPP_URL")
    
    if not web_app_url:
        return None
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Управление сессиями",
                    web_app=WebAppInfo(url=web_app_url)
                )
            ]
        ]
    )

# В handlers/commands.py или handlers/messages.py

@router.message(lambda m: m.text == "📋 Мои сессии")
async def sessions_button_handler(message: Message):
    """Обработка кнопки 'Мои сессии'"""
    # Показать список сессий и кнопку для открытия Mini App
    keyboard = get_miniapp_inline_keyboard()
    await message.answer(
        "📋 <b>Управление сессиями</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть Mini App для управления сессиями.",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )
```

## Связанные файлы

- `miniapp/` - структура Mini App
- `miniapp/api/` - REST API для Mini App
- `handlers/keyboards.py` - кнопка для открытия Mini App
- `handlers/webapp.py` - обработка данных от Mini App (если нужно)
- `database/base.py` - методы для работы с сессиями
- `config.py` - конфигурация (MINIAPP_URL, API_URL)

## Примечания

- **HTTPS обязателен** для Web Apps - Telegram требует HTTPS
- Для разработки можно использовать ngrok или другой туннель
- Для продакшена нужен реальный домен с SSL сертификатом
- Mini App должен быть доступен по публичному URL
- API должен быть защищен проверкой Telegram initData
- При переключении сессии из Mini App, пользователь возвращается в чат бота
- Сообщения в чате не изменяются, но новые сообщения будут в контексте выбранной сессии

## Этапы реализации

### Этап 1: Базовая структура (MVP)
- [ ] Создать структуру папок
- [ ] Создать базовый HTML с Telegram Web App API
- [ ] Создать простой API для получения списка сессий
- [ ] Реализовать отображение списка сессий
- [ ] Добавить кнопку для открытия Mini App в боте

### Этап 2: Просмотр сессий
- [ ] Реализовать API для получения сообщений сессии
- [ ] Реализовать отображение истории сообщений
- [ ] Реализовать форматирование Markdown
- [ ] Реализовать красивую верстку диалога

### Этап 3: Управление сессиями
- [ ] Реализовать переключение сессии
- [ ] Реализовать удаление сессии
- [ ] Реализовать завершение сессии
- [ ] Реализовать интеграцию с чатом бота

### Этап 4: Просмотр файлов базы знаний
- [ ] Реализовать API endpoint `GET /api/files/view?path=...` — получение содержимого файла
- [ ] Реализовать HTML-страницу с Markdown-рендерером (marked.js / markdown-it)
- [ ] Реализовать навигацию по файлам/папкам базы знаний
- [ ] Добавить кнопку `web_app=WebAppInfo(url=...)` в сообщения об изменениях файлов
- [ ] Реализовать поиск по файлам

### Этап 5: Улучшения
- [ ] Реализовать фильтрацию и поиск сессий
- [ ] Реализовать пагинацию
- [ ] Реализовать обновление в реальном времени
- [ ] Улучшить UI/UX

