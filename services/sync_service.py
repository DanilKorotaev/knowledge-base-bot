"""
Сервис синхронизации локальной копии базы знаний с NextCloud
"""
import asyncio
import logging
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from requests.auth import HTTPBasicAuth

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
        
        # Callback для прогресса синхронизации
        # Формат: async def progress(stage: str, current: int, total: int)
        self.progress_callback: Optional[Callable[[str, int, int], Awaitable[None]]] = None
        
        # Защита от спама уведомлений
        self._last_notify_time: Optional[datetime] = None
        self._notify_cooldown = timedelta(seconds=30)  # Минимум 30 секунд между уведомлениями
    
    def set_notify_callback(self, callback: Callable[[str, bool], Awaitable[None]]) -> None:
        """Установить callback для уведомлений о синхронизации"""
        self.notify_callback = callback
    
    def set_progress_callback(self, callback: Callable[[str, int, int], Awaitable[None]]) -> None:
        """Установить callback для прогресса синхронизации"""
        self.progress_callback = callback
    
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
                total = len(file_paths)
                uploaded = 0
                
                if self.progress_callback:
                    await self.progress_callback("upload", 0, total)
                
                for file_path in file_paths:
                    local_file = self.local_kb_path / file_path
                    if local_file.exists():
                        await self.nextcloud_service.upload_file(
                            local_file,
                            file_path
                        )
                        uploaded += 1
                        if self.progress_callback:
                            await self.progress_callback("upload", uploaded, total)
            else:
                # Синхронизировать все файлы (рекурсивно)
                # Сначала подсчитаем количество файлов
                total_files = await self._count_files(self.local_kb_path)
                
                if self.progress_callback:
                    await self.progress_callback("upload", 0, total_files)
                
                uploaded_count = [0]  # Используем список для передачи по ссылке
                await self._sync_directory_to_nextcloud(
                    self.local_kb_path, 
                    total_files=total_files,
                    uploaded_count=uploaded_count
                )
            
            logger.info("Синхронизация в NextCloud завершена")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации в NextCloud: {e}", exc_info=True)
            return False
    
    async def _count_files(self, directory: Path) -> int:
        """Подсчитать количество файлов в директории (рекурсивно)"""
        count = 0
        for item in directory.iterdir():
            if item.is_file():
                # Пропустить служебные файлы
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                count += 1
            elif item.is_dir():
                # Пропустить служебные директории
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                count += await self._count_files(item)
        return count
    
    async def _should_upload_file(self, local_file: Path, remote_path: str) -> bool:
        """Проверить, нужно ли загружать файл (сравнить дату модификации)"""
        try:
            # Проверить, существует ли файл в NextCloud
            if not await self.nextcloud_service.file_exists(remote_path):
                return True  # Файл не существует в NextCloud, нужно загрузить
            
            # Получить дату модификации удаленного файла
            url = self.nextcloud_service._get_webdav_url(remote_path)
            auth = HTTPBasicAuth(self.nextcloud_service.username, self.nextcloud_service.password)
            
            response = requests.head(url=url, auth=auth, timeout=10)
            
            if response.status_code == 200:
                # Получить Last-Modified из заголовков
                remote_last_modified = response.headers.get('Last-Modified')
                if remote_last_modified:
                    remote_mtime = parsedate_to_datetime(remote_last_modified).timestamp()
                    local_mtime = local_file.stat().st_mtime
                    
                    # Загружать только если локальный файл новее
                    return local_mtime > remote_mtime
            
            # Если не удалось сравнить, загружаем для безопасности
            return True
        except Exception as e:
            logger.debug(f"Не удалось проверить дату модификации {remote_path}: {e}")
            # В случае ошибки загружаем файл
            return True
    
    async def _sync_directory_to_nextcloud(
        self, 
        local_dir: Path, 
        remote_base: str = "",
        total_files: Optional[int] = None,
        uploaded_count: List[int] = None,
        files_to_upload: Optional[List[tuple]] = None
    ) -> None:
        """Рекурсивная синхронизация директории в NextCloud"""
        if uploaded_count is None:
            uploaded_count = [0]
        if files_to_upload is None:
            files_to_upload = []
        
        # Собрать все файлы для загрузки
        for item in local_dir.iterdir():
            if item.is_file():
                # Пропустить служебные файлы
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                
                remote_path = f"{remote_base}/{item.name}".lstrip('/')
                files_to_upload.append((item, remote_path))
            elif item.is_dir():
                # Пропустить служебные директории
                if item.name.startswith('.') or item.name in ['.git', '.cursor']:
                    continue
                
                new_remote_base = f"{remote_base}/{item.name}".lstrip('/')
                await self._sync_directory_to_nextcloud(
                    item, 
                    new_remote_base, 
                    total_files=total_files,
                    uploaded_count=uploaded_count,
                    files_to_upload=files_to_upload
                )
        
        # Если это корневой вызов, загрузить файлы параллельно
        if remote_base == "":
            # Фильтровать файлы, которые нужно загрузить (параллельно)
            semaphore_check = asyncio.Semaphore(10)  # Больше для проверки
            
            async def check_file(local_file: Path, remote_path: str):
                async with semaphore_check:
                    if await self._should_upload_file(local_file, remote_path):
                        return (local_file, remote_path)
                    return None
            
            # Проверить все файлы параллельно
            check_tasks = [check_file(local_file, remote_path) for local_file, remote_path in files_to_upload]
            check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
            
            # Отфильтровать None и исключения
            files_to_sync = [result for result in check_results if result is not None and not isinstance(result, Exception)]
            
            # Загружать файлы параллельно (по 5 одновременно)
            semaphore_upload = asyncio.Semaphore(5)
            
            async def upload_with_semaphore(local_file: Path, remote_path: str):
                async with semaphore_upload:
                    try:
                        await self.nextcloud_service.upload_file(local_file, remote_path)
                        uploaded_count[0] += 1
                        if self.progress_callback and total_files:
                            await self.progress_callback("upload", uploaded_count[0], total_files)
                    except Exception as e:
                        logger.error(f"Ошибка при загрузке файла {remote_path}: {e}")
            
            # Загрузить все файлы параллельно
            if files_to_sync:
                tasks = [upload_with_semaphore(local_file, remote_path) for local_file, remote_path in files_to_sync]
                await asyncio.gather(*tasks, return_exceptions=True)
    
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
            total_files = len(files)
            downloaded = 0
            updated = 0
            processed = 0
            
            if self.progress_callback:
                await self.progress_callback("download", 0, total_files)
            
            # Фильтровать файлы, которые нужно скачать
            files_to_download = []
            for file_info in files:
                remote_path = file_info.get('path', '')
                if not remote_path:
                    continue
                
                local_path = self.local_kb_path / remote_path
                remote_last_modified = file_info.get('last_modified')
                
                # Проверить, нужно ли обновить файл
                needs_update = True
                if local_path.exists() and remote_last_modified:
                    try:
                        remote_mtime = parsedate_to_datetime(remote_last_modified).timestamp()
                        local_mtime = local_path.stat().st_mtime
                        
                        # Обновлять только если удаленный файл новее (с запасом в 1 секунду для погрешности)
                        needs_update = remote_mtime > (local_mtime + 1)
                    except Exception:
                        # Если не удалось сравнить, скачиваем для безопасности
                        needs_update = True
                elif not local_path.exists():
                    # Файл не существует локально, нужно скачать
                    needs_update = True
                else:
                    # Локальный файл существует, но нет даты модификации удаленного
                    needs_update = False
                
                if needs_update:
                    files_to_download.append((remote_path, local_path))
                else:
                    updated += 1
                    processed += 1
                    if self.progress_callback:
                        await self.progress_callback("download", processed, total_files)
            
            # Скачать файлы параллельно (по 5 одновременно)
            semaphore = asyncio.Semaphore(5)
            
            async def download_with_semaphore(remote_path: str, local_path: Path):
                async with semaphore:
                    success = await self.nextcloud_service.download_file(remote_path, local_path)
                    nonlocal downloaded, processed
                    if success:
                        downloaded += 1
                    processed += 1
                    if self.progress_callback:
                        await self.progress_callback("download", processed, total_files)
            
            # Скачать все файлы параллельно
            tasks = [download_with_semaphore(remote_path, local_path) for remote_path, local_path in files_to_download]
            await asyncio.gather(*tasks, return_exceptions=True)
            
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
    
    async def detect_conflicts(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Обнаружить конфликты синхронизации для файла
        
        Конфликт возникает, когда локальный и удаленный файлы отличаются
        (оба были изменены независимо).
        
        Args:
            file_path: Путь к файлу (относительно local_kb_path)
        
        Returns:
            dict: Информация о конфликте или None если конфликта нет
        """
        if not self.enabled:
            return None
        
        local_file = self.local_kb_path / file_path
        
        # Если локальный файл не существует, конфликта нет (просто нужно скачать)
        if not local_file.exists():
            return None
        
        # Проверить, существует ли файл в NextCloud
        if not await self.nextcloud_service.file_exists(file_path):
            return None
        
        try:
            # Вычислить хеш локального файла
            from utils.file_helpers import calculate_file_hash
            local_hash = calculate_file_hash(local_file)
            
            # Получить хеш удаленного файла
            remote_hash = await self.nextcloud_service.get_file_hash(file_path)
            
            if remote_hash is None:
                # Не удалось получить хеш удаленного файла
                return None
            
            # Если хеши отличаются, есть конфликт
            if local_hash != remote_hash:
                return {
                    "file_path": file_path,
                    "local_hash": local_hash,
                    "remote_hash": remote_hash,
                    "conflict": True,
                    "local_exists": True,
                    "remote_exists": True
                }
            
            return None
        except Exception as e:
            logger.error(f"Ошибка при обнаружении конфликтов для {file_path}: {e}")
            return None
    
    async def resolve_conflict(
        self,
        file_path: str,
        strategy: str = "local"
    ) -> bool:
        """
        Разрешить конфликт синхронизации
        
        Args:
            file_path: Путь к файлу (относительно local_kb_path)
            strategy: Стратегия разрешения конфликта:
                - "local" - использовать локальную версию (загрузить в NextCloud)
                - "remote" - использовать удаленную версию (скачать из NextCloud)
                - "merge" - попытка слияния (не реализовано, использует local)
        
        Returns:
            bool: True если конфликт разрешен
        """
        if not self.enabled:
            return False
        
        conflict = await self.detect_conflicts(file_path)
        if not conflict:
            return True  # Конфликта нет
        
        try:
            if strategy == "local":
                # Загрузить локальную версию в NextCloud
                local_file = self.local_kb_path / file_path
                if local_file.exists():
                    await self.nextcloud_service.upload_file(local_file, file_path)
                    logger.info(f"Конфликт разрешен (local): {file_path}")
                    return True
            elif strategy == "remote":
                # Скачать удаленную версию
                local_file = self.local_kb_path / file_path
                await self.nextcloud_service.download_file(file_path, local_file)
                logger.info(f"Конфликт разрешен (remote): {file_path}")
                return True
            elif strategy == "merge":
                # Пока не реализовано - используем local
                logger.warning(f"Стратегия merge не реализована, используется local для {file_path}")
                local_file = self.local_kb_path / file_path
                if local_file.exists():
                    await self.nextcloud_service.upload_file(local_file, file_path)
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Ошибка при разрешении конфликта для {file_path}: {e}")
            return False

