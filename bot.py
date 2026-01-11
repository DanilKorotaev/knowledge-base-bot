"""
Точка входа для Telegram бота
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    try:
        # Валидация конфигурации
        config.validate()
        
        # Инициализация бота и диспетчера
        bot = Bot(
            token=config.TELEGRAM_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        dp = Dispatcher()
        
        # Регистрация обработчиков
        from handlers import commands, messages, voice, media
        dp.include_router(commands.router)
        dp.include_router(voice.router)
        dp.include_router(media.router)
        dp.include_router(messages.router)  # В конце, чтобы обрабатывать все остальные сообщения
        
        logger.info("Бот запущен")
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

