# Руководство для разработчиков

## Структура проекта

```
knowledge-base-bot/
├── bot.py                      # Точка входа
├── config.py                   # Конфигурация
├── database/                   # Работа с БД
│   ├── base.py                 # Интерфейс DatabaseInterface
│   ├── postgresql_db.py        # Реализация PostgreSQL
│   └── sqlite_db.py            # Реализация SQLite
├── services/                    # Бизнес-логика
│   ├── cursor_cli_service.py   # Работа с Cursor CLI
│   ├── openai_service.py       # Работа с OpenAI API
│   └── ...
├── handlers/                    # Обработчики Telegram
│   ├── commands.py             # Команды бота
│   ├── messages.py             # Текстовые сообщения
│   └── ...
└── utils/                       # Утилиты
```

## Разработка

### Локальная разработка

1. Используйте SQLite для локальной разработки:
```bash
DB_TYPE=sqlite
DB_FILE=bot.db
```

2. Отключите синхронизацию с NextCloud:
```bash
ENABLE_SYNC=false
```

3. Укажите путь к локальной копии базы знаний:
```bash
LOCAL_KB_PATH=/path/to/your/local/knowledge-base
```

### Добавление новых функций

1. **Новые команды**: Добавьте в `handlers/commands.py`
2. **Новые сервисы**: Создайте в `services/`
3. **Новые утилиты**: Добавьте в `utils/`

### Тестирование

```bash
# Запуск бота в режиме разработки
python bot.py
```

## Стиль кода

- Используйте type hints
- Следуйте PEP 8
- Документируйте функции и классы
- Используйте логирование вместо print

## Git workflow

1. Создайте feature branch
2. Внесите изменения
3. Создайте pull request
4. После ревью - merge в main

