"""
Точка входа для Telegram бота
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
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
        
        # Инициализация сессии Telegram (при необходимости через прокси)
        session = None
        if config.TELEGRAM_PROXY:
            logger.info(f"Telegram API будет использовать прокси: {config.TELEGRAM_PROXY}")
            session = AiohttpSession(proxy=config.TELEGRAM_PROXY)

        # Инициализация бота и диспетчера
        bot = Bot(
            token=config.TELEGRAM_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=None)
        )
        dp = Dispatcher()
        
        # Регистрация обработчиков
        from handlers import commands, messages, voice, media, callbacks
        dp.include_router(commands.router)
        dp.include_router(callbacks.router)  # Обработка inline-кнопок
        dp.include_router(voice.router)
        dp.include_router(media.router)
        dp.include_router(messages.router)  # В конце, чтобы обрабатывать все остальные сообщения
        
        # Инициализация базы данных
        from utils.db_helpers import get_db, close_db
        db = await get_db()
        logger.info("База данных инициализирована")
        
        # Инициализация администраторов из конфигурации
        if config.ADMIN_TELEGRAM_IDS:
            logger.info("ADMIN_TELEGRAM_IDS учитываются только у уже привязанных аккаунтов")
            for admin_id in config.ADMIN_TELEGRAM_IDS:
                try:
                    existing = await db.get_user_by_telegram_id(admin_id)
                    if not existing or not existing.get("login"):
                        logger.info(
                            "Пропуск admin id %s: нет привязанного аккаунта приложения",
                            admin_id,
                        )
                        continue
                    await db.update_app_user_fields(
                        int(existing["id"]), role="admin", is_admin=True
                    )
                    logger.info("Администратор %s подтверждён", admin_id)
                except Exception as e:
                    logger.error(f"Ошибка при инициализации администратора {admin_id}: {e}")
        
        # Регистрация middleware для проверки доступа
        from middleware.access_control import AccessControlMiddleware
        dp.update.middleware(AccessControlMiddleware())
        logger.info("Middleware для проверки доступа зарегистрирован")
        
        # Общий каталог бота больше не синхронизируется в фоне.
        # Запрос привязанного пользователя тянет его vault через SyncService.for_user.
        logger.info("Периодическая синхронизация общего vault бота не запускается")
        
        logger.info("Бот запущен")
        
        # Запуск polling
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Закрыть соединения
        from utils.db_helpers import close_db
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

