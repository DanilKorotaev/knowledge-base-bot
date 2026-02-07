"""
Сервис для работы с Cursor CLI
"""
import asyncio
import subprocess
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from config import config

logger = logging.getLogger(__name__)


class CursorCLIService:
    """Сервис для работы с Cursor CLI"""
    
    def __init__(self, kb_path: Optional[Path] = None):
        self.kb_path = Path(kb_path) if kb_path else config.LOCAL_KB_PATH
        self.api_key = config.CURSOR_API_KEY or config.OPENAI_API_KEY
        self.model = config.CURSOR_MODEL
        
        # Убедиться, что директория существует
        if not self.kb_path.exists():
            logger.warning(f"Директория базы знаний не существует: {self.kb_path}")
            self.kb_path.mkdir(parents=True, exist_ok=True)
        
        # Создать .cursorignore для оптимизации производительности
        self._ensure_cursorignore()
        
        # Создать .cursor/rules/ и скопировать системные промпты (для оптимизации)
        self._ensure_cursor_rules()
        
        # Загрузить системный промпт один раз при инициализации
        self.system_prompt = self._load_system_prompt()
    
    def _ensure_cursorignore(self) -> None:
        """
        Скопировать файлы игнорирования в базу знаний для оптимизации сканирования
        
        Поддерживаются два типа файлов:
        - .cursorignore: полное исключение файлов (нельзя читать)
        - .cursorindexingignore: не индексировать, но можно читать по запросу
        
        Приоритет загрузки:
        1. Путь из переменной окружения CURSOR_IGNORE_PATH (если указан)
        2. Файл из проекта
        3. Если не найден, не создавать (пользователь может создать свой)
        """
        # Копируем оба типа файлов
        for ignore_file in [".cursorignore", ".cursorindexingignore"]:
            self._copy_ignore_file(ignore_file)
    
    def _copy_ignore_file(self, filename: str) -> None:
        """Скопировать файл игнорирования если он не существует"""
        dest = self.kb_path / filename
        
        # Если файл уже существует в БЗ, не перезаписываем его
        if dest.exists():
            logger.debug(f"{filename} уже существует в БЗ: {dest}")
            return
        
        # Проверяем, указан ли путь в переменной окружения
        env_var = f"CURSOR_{filename.upper().replace('.', '_')}_PATH"
        custom_path = os.getenv(env_var) or os.getenv("CURSOR_IGNORE_PATH") if filename == ".cursorignore" else None
        
        if custom_path:
            ignore_source = Path(custom_path)
            if not ignore_source.is_absolute():
                project_root = Path(__file__).parent.parent
                ignore_source = project_root / ignore_source
            if ignore_source.exists():
                import shutil
                shutil.copy2(ignore_source, dest)
                logger.info(f"Скопирован {filename} из указанного пути: {ignore_source}")
                return
            else:
                logger.warning(f"Указанный путь к {filename} не найден: {ignore_source}")
        
        # Пробуем загрузить из проекта
        project_root = Path(__file__).parent.parent
        project_ignore_path = project_root / filename
        if project_ignore_path.exists():
            import shutil
            shutil.copy2(project_ignore_path, dest)
            logger.info(f"Скопирован {filename} из проекта: {project_ignore_path}")
        else:
            logger.debug(f"Файл {filename} не найден в проекте (это нормально, можно создать свой)")
    
    def _ensure_cursor_rules(self) -> None:
        """Создать .cursor/rules/ и скопировать системные промпты"""
        rules_dir = self.kb_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Загрузить промпт бота
        bot_prompt = self._load_bot_prompt()
        if bot_prompt:
            bot_prompt_file = rules_dir / "bot-system-prompt.md"
            if not bot_prompt_file.exists() or bot_prompt_file.read_text(encoding="utf-8") != bot_prompt:
                bot_prompt_file.write_text(bot_prompt, encoding="utf-8")
                logger.info(f"Промпт бота скопирован в .cursor/rules/")
        
        # Загрузить промпт БЗ
        kb_prompt = self._load_kb_prompt()
        if kb_prompt:
            kb_prompt_file = rules_dir / "kb-system-prompt.md"
            if not kb_prompt_file.exists() or kb_prompt_file.read_text(encoding="utf-8") != kb_prompt:
                kb_prompt_file.write_text(kb_prompt, encoding="utf-8")
                logger.info(f"Промпт БЗ скопирован в .cursor/rules/")
    
    def _load_system_prompt(self) -> str:
        """
        Загрузить системные промпты (промпт бота + промпт БЗ)
        
        Приоритет загрузки промпта бота:
        1. Путь из переменной окружения BOT_SYSTEM_PROMPT_PATH (если указан)
        2. Файл из проекта: agent/system_prompt.md
        
        Приоритет загрузки промпта БЗ:
        1. Путь из переменной окружения KB_SYSTEM_PROMPT_PATH (если указан)
        2. Файл из базы знаний: Документация/Системный промпт.md
        3. Другие возможные пути (можно расширить)
        
        Returns:
            str: Объединенный системный промпт (промпт бота + промпт БЗ)
        """
        prompts = []
        
        # 1. Загрузить промпт бота
        bot_prompt = self._load_bot_prompt()
        if bot_prompt:
            prompts.append(bot_prompt)
        
        # 2. Загрузить промпт базы знаний
        kb_prompt = self._load_kb_prompt()
        if kb_prompt:
            prompts.append("---")
            prompts.append("# Системный промпт базы знаний")
            prompts.append("")
            prompts.append(kb_prompt)
        
        if not prompts:
            logger.warning("Системные промпты не найдены, будет использоваться только запрос пользователя")
            return ""
        
        return "\n\n".join(prompts)
    
    def _load_bot_prompt(self) -> str:
        """Загрузить системный промпт бота"""
        # Проверяем, указан ли путь в переменной окружения
        custom_path = os.getenv("BOT_SYSTEM_PROMPT_PATH")
        if custom_path:
            prompt_path = Path(custom_path)
            if not prompt_path.is_absolute():
                # Относительный путь - от проекта
                project_root = Path(__file__).parent.parent
                prompt_path = project_root / prompt_path
            if prompt_path.exists():
                logger.info(f"Загружен промпт бота из указанного пути: {prompt_path}")
                return prompt_path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Указанный путь к промпту бота не найден: {prompt_path}")
        
        # Загрузить из проекта
        project_root = Path(__file__).parent.parent
        project_prompt_path = project_root / "agent" / "system_prompt.md"
        if project_prompt_path.exists():
            logger.info(f"Загружен промпт бота из проекта: {project_prompt_path}")
            return project_prompt_path.read_text(encoding="utf-8")
        
        return ""
    
    def _load_kb_prompt(self) -> str:
        """Загрузить системный промпт базы знаний"""
        # Проверяем, указан ли путь в переменной окружения
        custom_path = os.getenv("KB_SYSTEM_PROMPT_PATH")
        if custom_path:
            prompt_path = Path(custom_path)
            if not prompt_path.is_absolute():
                # Относительный путь - от базы знаний
                prompt_path = self.kb_path / prompt_path
            if prompt_path.exists():
                logger.info(f"Загружен промпт БЗ из указанного пути: {prompt_path}")
                return prompt_path.read_text(encoding="utf-8")
            else:
                logger.warning(f"Указанный путь к промпту БЗ не найден: {prompt_path}")
        
        logger.debug("Промпт базы знаний не найден (это нормально, если БЗ не имеет системного промпта)")
        return ""
    
    async def create_chat(self) -> Optional[str]:
        """
        Создать новый чат в Cursor CLI, вернуть chatId (UUID)
        
        Returns:
            str: UUID чата или None при ошибке
        """
        env = os.environ.copy()
        env["CURSOR_API_KEY"] = self.api_key
        if not env.get("CURSOR_API_KEY") and config.OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = config.OPENAI_API_KEY
        
        try:
            process = await asyncio.create_subprocess_exec(
                "cursor-agent", "create-chat",
                cwd=str(self.kb_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                chat_id = stdout.decode().strip()
                if chat_id:
                    logger.info(f"Создан новый чат Cursor CLI: {chat_id}")
                    return chat_id
                else:
                    logger.warning("cursor-agent create-chat вернул пустой ответ")
                    return None
            else:
                error = stderr.decode().strip()
                logger.error(f"Ошибка при создании чата Cursor CLI (код: {process.returncode}): {error}")
                return None
        except FileNotFoundError:
            logger.error("Команда 'cursor-agent' не найдена для create-chat")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании чата Cursor CLI: {e}")
            return None
    
    async def process_query(
        self,
        query: str,
        session_id: Optional[int] = None,
        model: Optional[str] = None,
        session_messages: Optional[List[Dict[str, Any]]] = None,
        attached_files: Optional[List[Path]] = None,
        cursor_chat_id: Optional[str] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Обработать запрос через Cursor CLI
        
        Args:
            query: Текст запроса пользователя
            session_id: ID сессии (опционально)
            model: Модель для использования (опционально, по умолчанию из конфига)
            session_messages: История сообщений сессии для контекста (опционально)
            attached_files: Список путей к прикрепленным файлам (фото, документы) (опционально)
            cursor_chat_id: ID чата Cursor CLI для --resume (опционально)
        
        Returns:
            tuple: (ответ от AI, список изменений файлов)
        """
        logger.info(f"Обработка запроса через Cursor CLI: {query[:50]}...")
        
        if not self.api_key:
            error_msg = "API ключ не установлен. Установите CURSOR_API_KEY или OPENAI_API_KEY"
            logger.error(error_msg)
            return f"❌ Ошибка: {error_msg}", []
        
        # Логировать прикрепленные файлы
        if attached_files:
            logger.info(f"Прикреплено файлов: {len(attached_files)}")
            for i, file_path in enumerate(attached_files, 1):
                if file_path and file_path.exists():
                    file_size = file_path.stat().st_size
                    logger.info(f"  Файл {i}: {file_path.name} ({file_size} байт, путь: {file_path})")
                else:
                    logger.warning(f"  Файл {i}: {file_path} (не найден!)")
        else:
            logger.debug("Прикрепленных файлов нет")
        
        # Сохранить состояние файлов до выполнения (для отслеживания изменений)
        file_states_before = await self._save_file_states()
        
        # Определяем режим работы: --resume (встроенные сессии) или ручная передача истории
        use_resume = bool(cursor_chat_id)
        
        if use_resume:
            # Режим --resume: Cursor CLI сам помнит контекст, передаём только текущий запрос
            logger.info(f"Используется --resume с chatId: {cursor_chat_id}")
            full_query = self._build_query_with_files_only(query, attached_files)
        else:
            # Старый режим: передаём историю в промпте
            full_query = self._build_query_with_context(query, session_messages, attached_files)
        
        if self.system_prompt:
            logger.debug(f"Системные промпты доступны в .cursor/rules/ ({len(self.system_prompt)} символов)")
        
        # Подготовить команду
        # -p: prompt mode (интерактивный режим)
        # --force: принудительное выполнение
        cmd = ["cursor-agent", "-p", "--force"]
        
        # Добавить --resume, если есть cursor_chat_id
        if use_resume:
            cmd.extend(["--resume", cursor_chat_id])
        
        # Добавить модель, если указана конкретная (не auto)
        # Если model = "auto" или пустая — Cursor CLI сам выберет модель
        model_to_use = model or self.model
        if model_to_use and model_to_use.lower() != "auto":
            cmd.extend(["--model", model_to_use])
        else:
            logger.debug("Модель не указана или 'auto' — Cursor CLI выберет автоматически")
        
        # Дополнительные флаги для оптимизации (если доступны)
        # Можно добавить через переменные окружения для экспериментов
        additional_flags = os.getenv("CURSOR_CLI_EXTRA_FLAGS", "").strip()
        if additional_flags:
            cmd.extend(additional_flags.split())
        
        # Добавить полный запрос
        cmd.append(full_query)
        
        # Подготовить окружение с API ключом
        env = os.environ.copy()
        env["CURSOR_API_KEY"] = self.api_key
        # Также пробуем OPENAI_API_KEY для совместимости
        if not env.get("CURSOR_API_KEY") and config.OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = config.OPENAI_API_KEY
        
        # Таймаут из конфига (по умолчанию 10 минут)
        timeout = int(os.getenv("CURSOR_CLI_TIMEOUT", "600"))
        
        try:
            # Выполнить команду в директории базы знаний
            logger.info(f"Выполнение команды: {' '.join(cmd)}")
            logger.info(f"Рабочая директория: {self.kb_path}")
            logger.info(f"Таймаут: {timeout} секунд")
            logger.debug(f"API ключ установлен: {'Да' if self.api_key else 'Нет'}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.kb_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            logger.info(f"Процесс Cursor CLI запущен (PID: {process.pid})")
            
            # Собирать вывод в реальном времени
            stdout_chunks = []
            stderr_chunks = []
            
            async def read_stream(stream, chunks_list, stream_name):
                """Читать поток и логировать в реальном времени"""
                try:
                    while True:
                        chunk = await stream.read(1024)
                        if not chunk:
                            break
                        decoded = chunk.decode('utf-8', errors='ignore')
                        chunks_list.append(decoded)
                        # Логировать важные сообщения
                        if decoded.strip():
                            logger.debug(f"Cursor CLI {stream_name}: {decoded.strip()[:200]}")
                except Exception as e:
                    logger.warning(f"Ошибка при чтении {stream_name}: {e}")
            
            # Читать потоки параллельно
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        read_stream(process.stdout, stdout_chunks, "stdout"),
                        read_stream(process.stderr, stderr_chunks, "stderr"),
                        process.wait()
                    ),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Превышен таймаут ({timeout} секунд). Завершение процесса...")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError) as e:
                    logger.warning(f"Ошибка при завершении процесса: {e}")
                
                # Собрать весь вывод до таймаута
                stdout_text = ''.join(stdout_chunks)
                stderr_text = ''.join(stderr_chunks)
                
                logger.error(f"Вывод Cursor CLI (stdout): {stdout_text[:500]}")
                logger.error(f"Вывод Cursor CLI (stderr): {stderr_text[:500]}")
                
                error_msg = f"Превышено время ожидания ответа от Cursor CLI ({timeout} секунд)"
                if stderr_text:
                    error_msg += f"\n\nПоследние сообщения:\n{stderr_text[-500:]}"
                logger.error(error_msg)
                return f"❌ {error_msg}", []
            
            # Получить код возврата
            returncode = await process.wait() if process.returncode is None else process.returncode
            
            # Собрать весь вывод
            stdout_text = ''.join(stdout_chunks)
            stderr_text = ''.join(stderr_chunks)
            
            # Логировать вывод
            if stdout_text:
                logger.debug(f"Cursor CLI stdout (полный): {stdout_text[:1000]}")
            if stderr_text:
                logger.info(f"Cursor CLI stderr: {stderr_text[:1000]}")
            
            # Проверить код возврата
            if returncode != 0:
                error_msg = f"Ошибка выполнения Cursor CLI (код: {returncode})"
                if stderr_text:
                    error_msg += f"\n\nОшибка:\n{stderr_text}"
                logger.error(error_msg)
                return f"❌ {error_msg}", []
            
            # Получить ответ
            response = stdout_text.strip()
            
            # Если ответ пустой, использовать stderr как fallback
            if not response:
                response = stderr_text.strip()
                if not response:
                    response = "✅ Запрос обработан, но ответ пуст"
            
            # Получить изменения файлов
            changes = await self._get_file_changes(file_states_before)
            
            logger.info(f"Запрос обработан успешно. Изменений файлов: {len(changes)}")
            return response, changes
            
        except FileNotFoundError:
            error_msg = "Команда 'cursor-agent' не найдена. Убедитесь, что Cursor CLI установлен и доступен в PATH"
            logger.error(error_msg)
            return f"❌ {error_msg}", []
        except Exception as e:
            error_msg = f"Неожиданная ошибка при вызове Cursor CLI: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return f"❌ {error_msg}", []
    
    async def _save_file_states(self) -> Dict[str, str]:
        """Сохранить состояние файлов для отслеживания изменений"""
        file_states = {}
        try:
            # Простой способ - использовать git для отслеживания изменений
            # Если git не инициализирован, просто вернуть пустой словарь
            if (self.kb_path / ".git").exists():
                # Получить список всех файлов в git
                process = await asyncio.create_subprocess_exec(
                    "git", "ls-files",
                    cwd=str(self.kb_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await process.communicate()
                if process.returncode == 0:
                    files = stdout.decode('utf-8').strip().split('\n')
                    for file_path in files:
                        if file_path:
                            full_path = self.kb_path / file_path
                            if full_path.exists():
                                try:
                                    file_states[str(full_path)] = full_path.read_text(encoding='utf-8', errors='ignore')
                                except Exception:
                                    pass
        except Exception as e:
            logger.debug(f"Не удалось сохранить состояние файлов: {e}")
        
        return file_states
    
    async def _get_file_changes(self, file_states_before: Dict[str, str]) -> List[Dict[str, Any]]:
        """Получить список измененных файлов"""
        changes = []
        
        try:
            # Попробовать использовать git diff
            if (self.kb_path / ".git").exists():
                process = await asyncio.create_subprocess_exec(
                    "git", "diff", "--name-only",
                    cwd=str(self.kb_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await process.communicate()
                if process.returncode == 0:
                    changed_files = stdout.decode('utf-8').strip().split('\n')
                    for file_path in changed_files:
                        if file_path:
                            full_path = self.kb_path / file_path
                            if full_path.exists():
                                try:
                                    new_content = full_path.read_text(encoding='utf-8', errors='ignore')
                                    old_content = file_states_before.get(str(full_path), "")
                                    
                                    change_type = "modified"
                                    if str(full_path) not in file_states_before:
                                        change_type = "created"
                                    
                                    changes.append({
                                        "path": file_path,
                                        "type": change_type,
                                        "old_content": old_content,
                                        "new_content": new_content
                                    })
                                except Exception as e:
                                    logger.debug(f"Ошибка при чтении файла {file_path}: {e}")
            
            # Если git не используется, попробовать сравнить с сохраненными состояниями
            if not changes:
                for file_path, old_content in file_states_before.items():
                    full_path = Path(file_path)
                    if full_path.exists():
                        try:
                            new_content = full_path.read_text(encoding='utf-8', errors='ignore')
                            if old_content != new_content:
                                changes.append({
                                    "path": str(full_path.relative_to(self.kb_path)),
                                    "type": "modified",
                                    "old_content": old_content,
                                    "new_content": new_content
                                })
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Ошибка при получении изменений файлов: {e}")
        
        return changes
    
    async def get_file_changes(self) -> List[Dict[str, Any]]:
        """Получить список измененных файлов (через git diff)"""
        return await self._get_file_changes({})
    
    def _build_query_with_files_only(
        self,
        query: str,
        attached_files: Optional[List[Path]] = None
    ) -> str:
        """
        Построить запрос только с прикрепленными файлами (без истории).
        Используется в режиме --resume, где Cursor CLI сам помнит контекст.
        
        Args:
            query: Текущий запрос пользователя
            attached_files: Список путей к прикрепленным файлам
        
        Returns:
            str: Запрос с упоминанием файлов (без истории)
        """
        if not attached_files:
            return query
        
        file_paths_in_prompt = []
        for file_path in attached_files:
            if file_path and file_path.exists():
                try:
                    relative_path = file_path.relative_to(self.kb_path)
                    file_paths_in_prompt.append(str(relative_path))
                except ValueError:
                    file_paths_in_prompt.append(str(file_path))
        
        if file_paths_in_prompt:
            files_list = ", ".join(file_paths_in_prompt)
            return f"{query}\n\n[Прикрепленные файлы для анализа: {files_list}]"
        
        return query
    
    def _build_query_with_context(
        self,
        query: str,
        session_messages: Optional[List[Dict[str, Any]]] = None,
        attached_files: Optional[List[Path]] = None
    ) -> str:
        """
        Построить запрос с контекстом сессии и прикрепленными файлами
        
        Args:
            query: Текущий запрос пользователя
            session_messages: История сообщений сессии
            attached_files: Список путей к прикрепленным файлам
        
        Returns:
            str: Запрос с контекстом и упоминанием файлов
        """
        # Обработать прикрепленные файлы
        # Согласно документации Cursor CLI: https://cursor.com/docs/cli/headless
        # Нужно просто упомянуть пути к файлам в промпте, и Cursor CLI автоматически прочитает их
        file_paths_in_prompt = []
        if attached_files:
            for file_path in attached_files:
                if file_path and file_path.exists():
                    # Преобразовать путь в относительный от базы знаний
                    try:
                        relative_path = file_path.relative_to(self.kb_path)
                        file_paths_in_prompt.append(str(relative_path))
                        logger.debug(f"Добавлен файл в промпт: {relative_path}")
                    except ValueError:
                        # Если файл не в базе знаний, используем абсолютный путь
                        file_paths_in_prompt.append(str(file_path))
                        logger.debug(f"Добавлен файл в промпт (абсолютный путь): {file_path}")
                else:
                    logger.warning(f"Файл не найден, пропускаем: {file_path}")
        
        # Если нет истории или только одно сообщение (текущий запрос), вернуть запрос без контекста
        if not session_messages or len(session_messages) <= 1:
            logger.debug("Нет предыдущих сообщений в сессии, отправляю запрос без контекста")
            # Добавить файлы в запрос, если есть
            if file_paths_in_prompt:
                # Добавляем файлы в запрос, как рекомендует документация
                # Cursor CLI автоматически прочитает файлы через tool calling
                files_list = ", ".join(file_paths_in_prompt)
                query_with_files = f"{query}\n\n[Прикрепленные файлы для анализа: {files_list}]"
                logger.info(f"Добавлено {len(file_paths_in_prompt)} файлов в промпт: {files_list}")
                return query_with_files
            return query
        
        # Фильтровать сообщения: исключить последнее, если оно совпадает с текущим запросом
        # (это может быть текущий запрос, который уже сохранился в БД)
        previous_messages = session_messages[:-1] if len(session_messages) > 1 else []
        
        # Если после фильтрации не осталось сообщений, вернуть запрос без контекста
        if not previous_messages:
            logger.debug("Нет предыдущих сообщений после фильтрации, отправляю запрос без контекста")
            # Добавить файлы в запрос, если есть
            if file_paths_in_prompt:
                # Добавляем файлы в запрос, как рекомендует документация
                # Cursor CLI автоматически прочитает файлы через tool calling
                files_list = ", ".join(file_paths_in_prompt)
                query_with_files = f"{query}\n\n[Прикрепленные файлы для анализа: {files_list}]"
                logger.info(f"Добавлено {len(file_paths_in_prompt)} файлов в промпт: {files_list}")
                return query_with_files
            return query
        
        # Ограничить количество сообщений для контекста (последние N сообщений)
        max_context_messages = 10
        context_messages = previous_messages[-max_context_messages:] if len(previous_messages) > max_context_messages else previous_messages
        
        # Построить контекст из истории
        context_parts = []
        context_parts.append("Контекст предыдущих сообщений в этой сессии:")
        context_parts.append("")
        
        for msg in context_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Ограничить длину каждого сообщения для контекста
            content_preview = content[:500] + "..." if len(content) > 500 else content
            role_label = "Пользователь" if role == "user" else "Ассистент"
            context_parts.append(f"{role_label}: {content_preview}")
        
        context_parts.append("")
        context_parts.append("---")
        context_parts.append("")
        context_parts.append(f"Текущий запрос пользователя: {query}")
        
        # Добавить файлы в конец запроса
        if file_paths_in_prompt:
            context_parts.append("")
            context_parts.append(f"Прикрепленные файлы для анализа: {', '.join(file_paths_in_prompt)}")
            logger.info(f"Добавлено {len(file_paths_in_prompt)} файлов в промпт: {', '.join(file_paths_in_prompt)}")
        
        full_query = "\n".join(context_parts)
        logger.debug(f"Построен запрос с контекстом ({len(context_messages)} предыдущих сообщений)")
        
        return full_query
    
    def setup_cursor_rules(self, kb_config: Optional[Dict[str, Any]] = None) -> None:
        """
        Создать структуру .cursor/rules/ с системными промптами
        
        Args:
            kb_config: Конфигурация БЗ (опционально, для универсальности)
        """
        rules_dir = self.kb_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Специальный промпт для Telegram бота (универсальный)
        bot_prompt = rules_dir / "telegram-bot-prompt.md"
        if not bot_prompt.exists():
            bot_prompt.write_text("""# Системный промпт для Telegram-бота

Ты - AI-ассистент, работающий внутри Telegram-бота для взаимодействия с базой знаний.

## О боте
- Название: Telegram Knowledge Base Bot
- Назначение: Интерфейс между пользователем и базой знаний через Telegram

## Как ты работаешь
1. Пользователь отправляет запрос в Telegram бота
2. Бот передает запрос тебе через Cursor CLI
3. Ты обрабатываешь запрос с учетом контекста базы знаний
4. Ты можешь читать, искать и изменять файлы в базе знаний
5. Результат возвращается пользователю через бота

## Формат ответа
- Отвечай на русском языке (или языке пользователя)
- Используй Markdown форматирование
- Будь кратким, но информативным

## Контекст базы знаний
База знаний находится в этой директории. Структура и правила работы описаны в:
- Системных промптах в `.cursor/rules/`
- Документации базы знаний (если есть)
- Файлах конфигурации (если есть)
""")
        
        # Если есть конфигурация БЗ, создать специфичный промпт
        if kb_config:
            kb_specific = rules_dir / "knowledge-base-config.md"
            import json
            kb_specific.write_text(f"""# Конфигурация базы знаний

{json.dumps(kb_config, indent=2, ensure_ascii=False)}
""")

