"""
Сервис для работы с NextCloud через WebDAV API
"""
import logging
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List, Dict, Any
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin, quote, unquote

from config import config

logger = logging.getLogger(__name__)


class NextCloudService:
    """Сервис для работы с NextCloud через WebDAV"""
    
    def __init__(self):
        self.url = config.NEXTCLOUD_URL
        self.username = config.NEXTCLOUD_BOT_USERNAME
        self.password = config.NEXTCLOUD_BOT_PASSWORD
        self.base_path = config.NEXTCLOUD_KNOWLEDGE_BASE_PATH
        
        if not self.url or not self.username or not self.password:
            logger.warning("NextCloud не настроен. Синхронизация будет отключена.")
            self.enabled = False
        else:
            self.enabled = True
            # Убрать trailing slash из URL
            self.url = self.url.rstrip('/')
            # WebDAV base URL
            self.webdav_url = f"{self.url}/remote.php/dav/files/{self.username}"
            # Убрать leading slash из base_path
            self.base_path = self.base_path.lstrip('/')
    
    def _get_full_path(self, relative_path: str) -> str:
        """Получить полный путь в NextCloud"""
        if self.base_path:
            return f"{self.base_path}/{relative_path}".lstrip('/')
        return relative_path.lstrip('/')
    
    def _get_webdav_url(self, relative_path: str = "") -> str:
        """Получить WebDAV URL для файла/папки"""
        if relative_path:
            full_path = self._get_full_path(relative_path)
            return f"{self.webdav_url}/{quote(full_path)}"
        return f"{self.webdav_url}/{quote(self.base_path)}" if self.base_path else self.webdav_url
    
    def _make_request(
        self,
        method: str,
        relative_path: str = "",
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """Выполнить WebDAV запрос"""
        if not self.enabled:
            raise ValueError("NextCloud не настроен")
        
        url = self._get_webdav_url(relative_path)
        auth = HTTPBasicAuth(self.username, self.password)
        
        default_headers = {
            'Content-Type': 'application/octet-stream'
        }
        if headers:
            default_headers.update(headers)
        
        try:
            response = requests.request(
                method=method,
                url=url,
                auth=auth,
                data=data,
                headers=default_headers,
                timeout=30
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к NextCloud: {e}")
            raise
    
    async def download_file(self, remote_path: str, local_path: Path) -> bool:
        """
        Скачать файл из NextCloud
        
        Args:
            remote_path: Путь к файлу в NextCloud (относительно base_path)
            local_path: Локальный путь для сохранения
        
        Returns:
            bool: True если успешно
        """
        if not self.enabled:
            return False
        
        try:
            response = self._make_request('GET', remote_path)
            
            # Создать директорию, если не существует
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Сохранить файл
            local_path.write_bytes(response.content)
            logger.info(f"Файл скачан: {remote_path} -> {local_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при скачивании файла {remote_path}: {e}")
            return False
    
    def _ensure_remote_directory(self, remote_dir_path: str) -> None:
        """
        Создать директорию в NextCloud (рекурсивно, если нужно).
        Используется MKCOL запрос. Игнорирует ошибку, если директория уже существует (405).
        
        Args:
            remote_dir_path: Путь к директории (относительно base_path)
        """
        if not remote_dir_path or remote_dir_path == '/':
            return
        
        # Собрать все уровни пути
        parts = Path(remote_dir_path).parts
        current_path = ""
        
        for part in parts:
            current_path = f"{current_path}/{part}".lstrip('/')
            url = self._get_webdav_url(current_path)
            auth = HTTPBasicAuth(self.username, self.password)
            
            try:
                response = requests.request(
                    method='MKCOL',
                    url=url,
                    auth=auth,
                    timeout=15
                )
                # 201 Created, 405 Already Exists — оба варианта OK
                if response.status_code in (201, 405):
                    continue
                elif response.status_code == 409:
                    # Родительская директория не существует — странно, мы идём рекурсивно
                    logger.warning(f"MKCOL 409 для {current_path}")
                else:
                    logger.debug(f"MKCOL {current_path}: статус {response.status_code}")
            except Exception as e:
                logger.debug(f"Ошибка MKCOL для {current_path}: {e}")
    
    async def upload_file(self, local_path: Path, remote_path: str) -> bool:
        """
        Загрузить файл в NextCloud.
        Автоматически создаёт родительские директории, если они не существуют.
        
        Args:
            local_path: Локальный путь к файлу
            remote_path: Путь в NextCloud (относительно base_path)
        
        Returns:
            bool: True если успешно
        """
        if not self.enabled:
            return False
        
        if not local_path.exists():
            logger.warning(f"Файл не существует: {local_path}")
            return False
        
        try:
            file_content = local_path.read_bytes()
            
            try:
                self._make_request('PUT', remote_path, data=file_content)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 409:
                    # 409 Conflict — родительская директория не существует
                    # Создать директории и повторить загрузку
                    parent_dir = str(Path(remote_path).parent)
                    logger.info(f"Создаю директорию в NextCloud: {parent_dir}")
                    self._ensure_remote_directory(parent_dir)
                    self._make_request('PUT', remote_path, data=file_content)
                else:
                    raise
            
            logger.info(f"Файл загружен: {local_path} -> {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла {local_path}: {e}")
            return False
    
    async def list_files(self, remote_path: str = "", recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Получить список файлов в директории
        
        Args:
            remote_path: Путь к директории (относительно base_path)
            recursive: Рекурсивно получать файлы из поддиректорий
        
        Returns:
            List[Dict]: Список файлов с метаданными
        """
        if not self.enabled:
            return []
        
        try:
            # PROPFIND запрос для получения списка файлов
            # Depth: 0 - только сам ресурс, 1 - первый уровень, infinity - рекурсивно
            depth = 'infinity' if recursive else '1'
            headers = {
                'Depth': depth,
                'Content-Type': 'application/xml'
            }
            
            propfind_body = '''<?xml version="1.0"?>
            <d:propfind xmlns:d="DAV:">
                <d:prop>
                    <d:getlastmodified/>
                    <d:getcontentlength/>
                    <d:resourcetype/>
                </d:prop>
            </d:propfind>'''
            
            url = self._get_webdav_url(remote_path)
            auth = HTTPBasicAuth(self.username, self.password)
            
            response = requests.request(
                method='PROPFIND',
                url=url,
                auth=auth,
                data=propfind_body,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # Парсинг XML ответа
            files = self._parse_propfind_response(response.text, remote_path)
            
            return files
        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов {remote_path}: {e}")
            return []
    
    async def file_exists(self, remote_path: str) -> bool:
        """
        Проверить существование файла в NextCloud
        
        Args:
            remote_path: Путь к файлу (относительно base_path)
        
        Returns:
            bool: True если файл существует
        """
        if not self.enabled:
            return False
        
        try:
            response = self._make_request('HEAD', remote_path)
            return response.status_code == 200
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise
        except Exception:
            return False
    
    def _parse_propfind_response(self, xml_content: str, base_path: str = "") -> List[Dict[str, Any]]:
        """
        Парсить XML ответ от PROPFIND запроса
        
        Args:
            xml_content: XML содержимое ответа
            base_path: Базовый путь (для относительных путей)
        
        Returns:
            List[Dict]: Список файлов с метаданными
        """
        files = []
        
        try:
            # Парсинг XML
            root = ET.fromstring(xml_content)
            
            # Namespace для WebDAV
            namespaces = {
                'd': 'DAV:',
                'oc': 'http://owncloud.org/ns',
                'nc': 'http://nextcloud.org/ns'
            }
            
            # Найти все response элементы
            for response in root.findall('.//d:response', namespaces):
                href_elem = response.find('d:href', namespaces)
                if href_elem is None:
                    continue
                
                href = unquote(href_elem.text or '')
                
                # Пропустить сам каталог (если это директория)
                if href.endswith('/'):
                    continue
                
                # Получить относительный путь
                # href имеет формат: /remote.php/dav/files/username/path/to/file
                # Нужно извлечь только path/to/file (относительно base_path)
                webdav_prefix = f"/remote.php/dav/files/{self.username}/"
                if webdav_prefix in href:
                    full_path = href.split(webdav_prefix, 1)[1]
                else:
                    # Fallback: использовать href как есть
                    full_path = href.lstrip('/')
                
                # Убрать base_path из начала пути, если он там есть
                # base_path уже учтен в webdav_url, поэтому нужно получить путь относительно base_path
                relative_path = full_path
                if self.base_path:
                    base_path_normalized = self.base_path.lstrip('/').rstrip('/')
                    if relative_path.startswith(base_path_normalized + '/'):
                        relative_path = relative_path[len(base_path_normalized) + 1:]
                    elif relative_path == base_path_normalized:
                        relative_path = ""
                
                # Получить метаданные
                propstat = response.find('d:propstat', namespaces)
                if propstat is None:
                    continue
                
                prop = propstat.find('d:prop', namespaces)
                if prop is None:
                    continue
                
                # Извлечь информацию о файле
                last_modified = prop.find('d:getlastmodified', namespaces)
                content_length = prop.find('d:getcontentlength', namespaces)
                resource_type = prop.find('d:resourcetype', namespaces)
                
                # Проверить, что это файл, а не директория
                if resource_type is not None:
                    collection = resource_type.find('d:collection', namespaces)
                    if collection is not None:
                        continue  # Пропустить директории
                
                file_info = {
                    'path': relative_path,
                    'href': href,
                    'last_modified': last_modified.text if last_modified is not None else None,
                    'size': int(content_length.text) if content_length is not None and content_length.text else 0,
                }
                
                files.append(file_info)
            
            logger.debug(f"Найдено файлов в {base_path}: {len(files)}")
            return files
            
        except ET.ParseError as e:
            logger.error(f"Ошибка при парсинге XML ответа: {e}")
            return []
        except Exception as e:
            logger.error(f"Неожиданная ошибка при парсинге XML: {e}", exc_info=True)
            return []
    
    async def delete_file(self, remote_path: str) -> bool:
        """
        Удалить файл в NextCloud
        
        Args:
            remote_path: Путь к файлу (относительно base_path)
        
        Returns:
            bool: True если успешно
        """
        if not self.enabled:
            return False
        
        try:
            self._make_request('DELETE', remote_path)
            logger.info(f"Файл удален: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {remote_path}: {e}")
            return False
    
    async def get_file_hash(self, remote_path: str) -> Optional[str]:
        """
        Получить хеш файла из NextCloud (через ETag или скачивание)
        
        Args:
            remote_path: Путь к файлу (относительно base_path)
        
        Returns:
            str: Хеш файла (SHA256) или None если не удалось получить
        """
        if not self.enabled:
            return None
        
        try:
            # Попробовать получить ETag из заголовков (более эффективно)
            url = self._get_webdav_url(remote_path)
            auth = HTTPBasicAuth(self.username, self.password)
            
            response = requests.head(
                url=url,
                auth=auth,
                timeout=10
            )
            
            if response.status_code == 200:
                # NextCloud может возвращать ETag, но он не всегда является хешем файла
                # Поэтому скачаем файл и вычислим хеш
                file_content = await self.read_file(remote_path)
                if file_content:
                    import hashlib
                    return hashlib.sha256(file_content.encode('utf-8')).hexdigest()
            
            return None
        except Exception as e:
            logger.debug(f"Не удалось получить хеш файла {remote_path}: {e}")
            return None
    
    async def read_file(self, remote_path: str) -> Optional[str]:
        """
        Прочитать содержимое файла из NextCloud
        
        Args:
            remote_path: Путь к файлу (относительно base_path)
        
        Returns:
            str: Содержимое файла или None если не удалось прочитать
        """
        if not self.enabled:
            return None
        
        try:
            response = self._make_request('GET', remote_path)
            return response.text
        except Exception as e:
            logger.debug(f"Не удалось прочитать файл {remote_path}: {e}")
            return None

