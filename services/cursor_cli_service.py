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
        
        # Убедиться, что системный промпт скопирован в .cursor/rules/
        self._ensure_system_prompt()
    
    def _ensure_system_prompt(self) -> None:
        """Убедиться, что системный промпт бота скопирован в .cursor/rules/"""
        rules_dir = self.kb_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        
        # Путь к системному промпту в проекте
        project_root = Path(__file__).parent.parent
        system_prompt_source = project_root / "agent" / "system_prompt.md"
        
        # Путь назначения
        system_prompt_dest = rules_dir / "telegram-bot-prompt.md"
        
        # Копировать системный промпт, если он существует и еще не скопирован
        if system_prompt_source.exists():
            if not system_prompt_dest.exists() or system_prompt_source.stat().st_mtime > system_prompt_dest.stat().st_mtime:
                import shutil
                shutil.copy2(system_prompt_source, system_prompt_dest)
                logger.info(f"Системный промпт скопирован в {system_prompt_dest}")
        else:
            logger.warning(f"Системный промпт не найден: {system_prompt_source}")
    
    def _load_system_prompt(self) -> str:
        """Загрузить системный промпт из файла"""
        # Сначала пробуем загрузить из проекта
        project_root = Path(__file__).parent.parent
        system_prompt_path = project_root / "agent" / "system_prompt.md"
        
        if system_prompt_path.exists():
            return system_prompt_path.read_text(encoding="utf-8")
        
        # Если не найден, пробуем из .cursor/rules/
        rules_prompt_path = self.kb_path / ".cursor" / "rules" / "telegram-bot-prompt.md"
        if rules_prompt_path.exists():
            return rules_prompt_path.read_text(encoding="utf-8")
        
        logger.warning("Системный промпт не найден, используется пустая строка")
        return ""
    
    async def process_query(
        self,
        query: str,
        session_id: Optional[int] = None,
        model: Optional[str] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Обработать запрос через Cursor CLI
        
        Args:
            query: Текст запроса пользователя
            session_id: ID сессии (опционально)
            model: Модель для использования (опционально, по умолчанию из конфига)
        
        Returns:
            tuple: (ответ от AI, список изменений файлов)
        """
        logger.info(f"Обработка запроса через Cursor CLI: {query[:50]}...")
        
        if not self.api_key:
            error_msg = "API ключ не установлен. Установите CURSOR_API_KEY или OPENAI_API_KEY"
            logger.error(error_msg)
            return f"❌ Ошибка: {error_msg}", []
        
        # Сохранить состояние файлов до выполнения (для отслеживания изменений)
        file_states_before = await self._save_file_states()
        
        # Подготовить команду
        cmd = ["cursor-agent", "-p", "--force"]
        
        # Добавить модель, если указана
        model_to_use = model or self.model
        if model_to_use:
            cmd.extend(["--model", model_to_use])
        
        # Добавить запрос
        cmd.append(query)
        
        # Подготовить окружение с API ключом
        env = os.environ.copy()
        env["CURSOR_API_KEY"] = self.api_key
        # Также пробуем OPENAI_API_KEY для совместимости
        if not env.get("CURSOR_API_KEY") and config.OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = config.OPENAI_API_KEY
        
        try:
            # Выполнить команду в директории базы знаний
            logger.debug(f"Выполнение команды: {' '.join(cmd)}")
            logger.debug(f"Рабочая директория: {self.kb_path}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.kb_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Ждать завершения с таймаутом (5 минут)
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300.0
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                error_msg = "Превышено время ожидания ответа от Cursor CLI (5 минут)"
                logger.error(error_msg)
                return f"❌ {error_msg}", []
            
            # Проверить код возврата
            if process.returncode != 0:
                error_msg = f"Ошибка выполнения Cursor CLI: {stderr.decode('utf-8', errors='ignore')}"
                logger.error(error_msg)
                return f"❌ {error_msg}", []
            
            # Получить ответ
            response = stdout.decode('utf-8', errors='ignore').strip()
            
            # Если ответ пустой, использовать stderr как fallback
            if not response:
                response = stderr.decode('utf-8', errors='ignore').strip()
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

