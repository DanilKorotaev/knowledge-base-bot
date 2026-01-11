"""
Сервис синхронизации локальной копии базы знаний с NextCloud
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta

from config import config
from services.nextcloud_service import NextCloudService

logger = logging.getLogger(__name__)


class SyncService:
    """Сервис синхронизации с NextCloud"""
    
    def __init__(self, local_kb_path: Optional[Path] = None):
        self.local_kb_path = local_kb_path or config.LOCAL_KB_PATH
        self.nextcloud_service = NextCloudService()
        self.enabled = config.ENABLE_SYNC and self.nextcloud_service.enabled
        self.sync_interval = config.SYNC_INTERVAL
        self._sync_task: Optional[asyncio.Task] = None
        
        # Callback для уведомлений о синхронизации
        # Формат: async def notify(message: str, is_important: bool = False)
        self.notify_callback: Optional[Callable[[str, bool], Awaitable[None]]] = None
        
        # Защита от спама уведомлений
        self._last_notify_time: Optional[datetime] = None
        self._notify_cooldown = timedelta(seconds=30)  # Минимум 30 секунд между уведомлениями
    
    def set_notify_callback(self, callback: Callable[[str, bool], Awaitable[None]]) -> None:
        """Установить callback для уведомлений о синхронизации"""
        self.notify_callback = callback
    
    async def _notify(self, message: str, is_important: bool = False) -> None:
        """
        Отправить уведомление через callback (с защитой от спама)
        
        Args:
            message: Текст уведомления
            is_important: Если True, уведомление отправляется всегда (игнорирует cooldown)
        """
        if not self.notify_callback:
            return
        
        # Проверка cooldown (только для неважных уведомлений)
        if not is_important:
            now = datetime.now()
            if self._last_notify_time and (now - self._last_notify_time) < self._notify_cooldown:
                logger.debug(f"Пропущено уведомление (cooldown): {message}")
                return
            self._last_notify_time = now
        
        try:
            await self.notify_callback(message, is_important)
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления: {e}")
    
    async def check_and_sync_if_needed(self, force: bool = False) -> bool:
        """
        Проверить и синхронизировать, если нужно
        
        Args:
            force: Принудительная синхронизация
        
        Returns:
            bool: True если была синхронизация
        """
        if not self.enabled:
            return False
        
        # Упрощенная проверка: синхронизируем только если включена AUTO_SYNC
        # В будущем можно добавить проверку по времени последней синхронизации
        from config import config
        if not config.AUTO_SYNC and not force:
            return False
        
        return await self.sync_from_nextcloud(show_notification=True)
    
    async def initialize(self) -> bool:
        """
        Инициализация: скачать базу знаний из NextCloud, если локальная папка пустая
        
        Returns:
            bool: True если инициализация успешна
        """
        if not self.enabled:
            logger.info("Синхронизация отключена")
            return True
        
        # Проверить, существует ли локальная папка
        if not self.local_kb_path.exists():
            logger.info(f"Создание директории: {self.local_kb_path}")
            self.local_kb_path.mkdir(parents=True, exist_ok=True)
        
        # Проверить, пустая ли папка
        has_files = any(self.local_kb_path.iterdir())
        
        if not has_files:
            logger.info("Локальная папка пуста. Начинаю загрузку из NextCloud...")
            # При инициализации не показываем уведомления (пользователь еще не подключен)
            result = await self.sync_from_nextcloud(show_notification=False)
            if result:
                logger.info("✅ База знаний загружена из NextCloud")
            else:
                logger.warning("⚠️ Не удалось загрузить базу знаний из NextCloud")
            return result
        else:
            logger.info(f"Локальная папка уже содержит файлы: {self.local_kb_path}")
            return True
    
    async def sync_to_nextcloud(self, file_paths: Optional[List[str]] = None) -> bool:
        """
        Синхронизировать изменения в NextCloud (загрузить измененные файлы)
        
        Args:
            file_paths: Список путей к файлам для синхронизации (относительно local_kb_path).
                       Если None, синхронизируются все измененные файлы.
        
        Returns:
            bool: True если синхронизация успешна
        """
        if not self.enabled:
            logger.debug("Синхронизация отключена")
            return False
        
        try:
            if file_paths:
                # Синхронизировать только указанные файлы
                for file_path in file_paths:
                    local_file = self.local_kb_path / file_path
                    if local_file.exists():
                        await self.nextcloud_service.upload_file(
                            local_file,
                            file_path
                        )
            else:
                # Синхронизировать все файлы (рекурсивно)
                await self._sync_directory_to_nextcloud(self.local_kb_path)
            
            logger.info("Синхронизация в NextCloud завершена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации в NextCloud: {e}", exc_info=True)
            return False
    
    async def _sync_directory_to_nextcloud(self, local_dir: Path, remote_base: str = "") -> None:
        """Рекурсивная синхронизация директории в NextCloud"""
        for item in local_dir.iterdir():
            if item.is_file():
                # Пропустить служебные файлы
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                
                remote_path = f"{remote_base}/{item.name}".lstrip('/')
                await self.nextcloud_service.upload_file(item, remote_path)
            elif item.is_dir():
                # Пропустить служебные директории
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                
                new_remote_base = f"{remote_base}/{item.name}".lstrip('/')
                await self._sync_directory_to_nextcloud(item, new_remote_base)
    
    async def sync_from_nextcloud(self, show_notification: bool = False) -> bool:
        """
        Синхронизировать изменения из NextCloud (скачать файлы)
        
        Args:
            show_notification: Показывать ли уведомление (только если синхронизация долгая)
        
        Returns:
            bool: True если синхронизация успешна
        """
        if not self.enabled:
            logger.debug("Синхронизация отключена")
            return False
        
        start_time = time.time()
        notification_shown = False
        
        try:
            # Получить список файлов из NextCloud (рекурсивно)
            files = await self.nextcloud_service.list_files(recursive=True)
            
            if not files:
                logger.warning("Не удалось получить список файлов из NextCloud. Возможно, папка пуста или нет доступа.")
                return False
            
            logger.info(f"Найдено файлов для синхронизации: {len(files)}")
            
            # Показать уведомление, если синхронизация долгая (> 2 секунд)
            if show_notification and len(files) > 10:
                elapsed = time.time() - start_time
                if elapsed > 2.0:
                    await self._notify("🔄 Синхронизирую изменения из NextCloud...")
                    notification_shown = True
            
            # Скачать файлы
            downloaded = 0
            updated = 0
            for file_info in files:
                remote_path = file_info.get('path', '')
                if not remote_path:
                    continue
                
                local_path = self.local_kb_path / remote_path
                
                # Проверить, нужно ли обновить файл (если локальный файл существует и старше)
                needs_update = True
                if local_path.exists():
                    # Упрощенная проверка: если файл существует, считаем что он актуален
                    # В будущем можно добавить проверку по дате модификации
                    needs_update = False
                
                if needs_update:
                    # Скачать файл
                    success = await self.nextcloud_service.download_file(remote_path, local_path)
                    if success:
                        downloaded += 1
                else:
                    updated += 1
            
            elapsed_time = time.time() - start_time
            
            if notification_shown and downloaded > 0:
                await self._notify(f"✅ Синхронизировано: {downloaded} новых файлов из NextCloud")
            elif downloaded > 0:
                logger.info(f"Синхронизация из NextCloud завершена. Скачано файлов: {downloaded}/{len(files)}")
            
            logger.info(f"Синхронизация из NextCloud завершена за {elapsed_time:.2f}с. Скачано: {downloaded}, актуально: {updated}")
            return downloaded > 0 or updated > 0
        except Exception as e:
            logger.error(f"Ошибка при синхронизации из NextCloud: {e}", exc_info=True)
            return False
    
    async def sync_file(self, file_path: str, direction: str = "both") -> bool:
        """
        Синхронизировать конкретный файл
        
        Args:
            file_path: Путь к файлу (относительно local_kb_path)
            direction: Направление синхронизации ("to", "from", "both")
        
        Returns:
            bool: True если синхронизация успешна
        """
        if not self.enabled:
            return False
        
        local_file = self.local_kb_path / file_path
        
        try:
            if direction in ["to", "both"]:
                if local_file.exists():
                    await self.nextcloud_service.upload_file(local_file, file_path)
            
            if direction in ["from", "both"]:
                await self.nextcloud_service.download_file(file_path, local_file)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации файла {file_path}: {e}")
            return False
    
    async def sync_changes(self, changes: List[Dict[str, Any]]) -> bool:
        """
        Синхронизировать список изменений
        
        Args:
            changes: Список изменений файлов (из cursor_cli_service)
        
        Returns:
            bool: True если синхронизация успешна
        """
        if not self.enabled or not changes:
            return False
        
        try:
            file_paths = [change['path'] for change in changes]
            return await self.sync_to_nextcloud(file_paths)
        except Exception as e:
            logger.error(f"Ошибка при синхронизации изменений: {e}")
            return False
    
    async def start_periodic_sync(self) -> None:
        """Запустить периодическую синхронизацию из NextCloud"""
        if not self.enabled or not config.AUTO_SYNC:
            return
        
        logger.info(f"Запуск периодической синхронизации (интервал: {self.sync_interval} сек)")
        
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                # Периодическая синхронизация без уведомлений (чтобы не спамить)
                await self.sync_from_nextcloud(show_notification=False)
            except asyncio.CancelledError:
                logger.info("Периодическая синхронизация остановлена")
                break
            except Exception as e:
                logger.error(f"Ошибка при периодической синхронизации: {e}")
    
    def stop_periodic_sync(self) -> None:
        """Остановить периодическую синхронизацию"""
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

