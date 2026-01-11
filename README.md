# Telegram Knowledge Base Bot

Telegram-бот для удобного взаимодействия с базой знаний Obsidian через AI-ассистента.

## Описание

Этот бот работает как интерфейс между пользователем и AI-ассистентом (Cursor CLI) для взаимодействия с базой знаний. Пользователь отправляет запрос в Telegram бота, бот передает запрос в Cursor CLI с контекстом базы знаний, AI обрабатывает запрос и может читать, искать и изменять файлы базы знаний.

## Основные возможности

- ✅ Обработка текстовых запросов с контекстом базы знаний
- ✅ Транскрибация голосовых сообщений (Whisper API)
- ✅ Обработка фото и файлов
- ✅ Интеграция с NextCloud для синхронизации
- ✅ Отслеживание изменений с возможностью отката
- ✅ Режим "пустого чата" и режим работы с базой знаний
- ✅ Универсальность: можно развернуть на любую базу знаний

## Быстрый старт

### Требования

- Python 3.11+
- PostgreSQL (или SQLite для локальной разработки)
- Cursor CLI (или OpenAI API ключ)
- NextCloud (опционально, для синхронизации)

### Установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/DanilKorotaev/knowledge-base-bot.git
cd knowledge-base-bot
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env файл
```

4. Запустите бота:
```bash
python bot.py
```

Подробные инструкции по установке и настройке см. в [docs/SETUP.md](docs/SETUP.md).

## Документация

- [SETUP.md](docs/SETUP.md) - Инструкции по установке и настройке
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - Руководство для разработчиков
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Инструкции по развертыванию
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Описание архитектуры
- [GIT_FLOW.md](docs/GIT_FLOW.md) - Процесс разработки и релизов
- [TODO.md](docs/todo.md) - Активные задачи
- [COMPLETED.md](docs/completed.md) - Выполненные задачи

## Структура проекта

```
knowledge-base-bot/
├── bot.py                      # Точка входа
├── config.py                   # Конфигурация
├── database/                   # Работа с БД
├── services/                   # Бизнес-логика
├── handlers/                   # Обработчики Telegram
├── utils/                      # Утилиты
├── docs/                       # Документация
├── .cursor/                    # Системные промпты для Cursor
└── docker-compose.yml          # Docker конфигурация
```

## Лицензия

MIT License

## Автор

DanilKorotaev

## Ссылки

- [GitHub Repository](https://github.com/DanilKorotaev/knowledge-base-bot)
- [Документация проекта](docs/)

