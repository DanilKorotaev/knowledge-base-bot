# Добавить pydantic-based settings для валидации конфигурации

**Статус**: 📋 Запланировано  
**Приоритет**: 🟡 Средний  
**Категория**: Технические улучшения

## Описание

Замена текущей системы конфигурации на pydantic-based settings для валидации и типизации.

## Цели

1. Заменить `config.py` на pydantic-based settings
2. Добавить валидацию всех переменных окружения
3. Улучшить типизацию конфигурации
4. Добавить автоматическую документацию настроек

## Задачи

- [ ] Установить `pydantic` и `pydantic-settings`
- [ ] Создать класс `Settings` с использованием `BaseSettings`
- [ ] Добавить валидацию для всех переменных окружения
- [ ] Добавить типизацию для всех настроек
- [ ] Обновить `config.py` для использования pydantic
- [ ] Обновить документацию с описанием всех настроек

## Пример реализации

```python
from pydantic import BaseSettings, Field, validator

class Settings(BaseSettings):
    # Telegram
    telegram_token: str = Field(..., env="TELEGRAM_TOKEN")
    
    # Cursor CLI / OpenAI API
    cursor_api_key: Optional[str] = Field(None, env="CURSOR_API_KEY")
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    
    @validator("cursor_api_key", "openai_api_key")
    def validate_api_key(cls, v, values):
        if not v and not values.get("openai_api_key"):
            raise ValueError("Необходимо установить CURSOR_API_KEY или OPENAI_API_KEY")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

## Связанные файлы

- `config.py` - конфигурация
- `requirements.txt` - зависимости

