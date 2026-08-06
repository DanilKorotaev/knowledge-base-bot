"""
Сервис для работы с Cursor CLI
"""
import asyncio
import logging
import os
import pty
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable, Awaitable
from config import config
from services.cursor_stream_parser import (
    StreamJsonAccumulator,
    parse_ndjson_line,
)
from utils.sync_path_filter import filter_trackable_changes, is_excluded_sync_path
from utils.terminal_sanitize import strip_terminal_escape_sequences

logger = logging.getLogger(__name__)

# Ответ при отмене пользователем (см. query_processing_service)
CURSOR_QUERY_CANCELLED_MESSAGE = "⏹ Обработка запроса отменена."

# Тексты для Telegram (без сырого stderr / traceback)
CURSOR_USER_TIMEOUT_FIRST_CHUNK = (
    "❌ Слишком долго нет ответа от ассистента (нет активности в потоке).\n\n"
    "Попробуйте упростить запрос, повторить позже или проверьте сеть. "
    "Для тяжёлых задач на сервере можно увеличить CURSOR_CLI_TIMEOUT."
)

CURSOR_USER_PROCESS_FAILED = (
    "❌ Ошибка при выполнении запроса (процесс завершился с ошибкой). "
    "Повторите попытку; если повторяется — сообщите администратору."
)

CURSOR_USER_MODEL_UNAVAILABLE = (
    "❌ Cursor CLI не смог выбрать модель (каталог моделей пуст или модель недоступна). "
    "Повторите попытку через минуту; если повторяется — проверьте VPN/прокси на сервере "
    "и что cursor-agent залогинен (agent status)."
)


def resolve_cursor_cli_model(model: Optional[str]) -> str:
    """
    Модель для флага cursor-agent --model.

    В IDE и в актуальном CLI пул Auto — ключ ``auto`` (``cursor-agent --list-models``:
    ``auto - Auto (current, default)``). Исторически CLI принимал ``default``; с ~2026.07
    ``--model default`` отвергается с пустым списком available models.
    Пустой / ``auto`` / ``default`` → ``auto``. Без --model CLI может уйти в API-модели.
    """
    raw = (model or "").strip()
    if not raw or raw.lower() in ("auto", "default"):
        return "auto"
    return raw


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
    
    def _prepare_env(self) -> dict:
        """Подготовить окружение для subprocess: API ключи"""
        env = os.environ.copy()
        env["CURSOR_API_KEY"] = self.api_key
        if not env.get("CURSOR_API_KEY") and config.OPENAI_API_KEY:
            env["OPENAI_API_KEY"] = config.OPENAI_API_KEY
        # cursor-agent (Node / global-agent): HTTP_PROXY и HTTPS_PROXY должны быть http:,
        # иначе «Unsupported ... URL protocol must be http:"» для socks5://.
        # Для SOCKS5 достаточно ALL_PROXY; HTTP(S)_PROXY не дублируем.
        proxy = config.CURSOR_CLI_PROXY or config.OPENAI_PROXY
        if proxy:
            pl = proxy.strip().lower()
            env["ALL_PROXY"] = proxy
            if pl.startswith("socks5://") or pl.startswith("socks://"):
                env.pop("HTTP_PROXY", None)
                env.pop("HTTPS_PROXY", None)
            else:
                env["HTTPS_PROXY"] = proxy
                env["HTTP_PROXY"] = proxy
        return env

    def _cmd_with_optional_stdbuf(self, cmd: list[str]) -> list[str]:
        """stdbuf есть в Linux (Docker); на macOS без GNU coreutils — запуск без обёртки."""
        use_stdbuf = os.getenv("CURSOR_CLI_USE_STDBUF", "true").lower() in ("true", "1", "yes")
        if not use_stdbuf:
            return cmd
        if shutil.which("stdbuf"):
            logger.debug("Используется stdbuf -oL для принудительного сброса буфера stdout")
            return ["stdbuf", "-oL", *cmd]
        logger.debug("stdbuf не найден в PATH — запуск cursor-agent без line-buffering")
        return cmd

    def _use_pty_for_stdout(self) -> bool:
        """macOS: pipe stdout is block-buffered; PTY gives line-ish streaming for on_chunk."""
        if self._cursor_output_format() == "stream-json":
            return False
        if sys.platform != "darwin":
            return False
        return os.getenv("CURSOR_CLI_USE_PTY", "true").lower() in ("true", "1", "yes")

    def _cursor_output_format(self) -> str:
        fmt = (config.CURSOR_CLI_OUTPUT_FORMAT or "text").strip().lower()
        if fmt not in ("text", "stream-json"):
            logger.warning("Неизвестный CURSOR_CLI_OUTPUT_FORMAT=%r, используем text", fmt)
            return "text"
        return fmt

    def _stream_partial_output_enabled(self) -> bool:
        return bool(config.CURSOR_CLI_STREAM_PARTIAL_OUTPUT)

    def _append_output_format_flags(self, cmd: list[str]) -> None:
        if self._cursor_output_format() == "stream-json":
            cmd.extend(["--output-format", "stream-json"])
            if self._stream_partial_output_enabled():
                cmd.append("--stream-partial-output")
            logger.info(
                "Cursor CLI: output-format=stream-json (partial=%s)",
                self._stream_partial_output_enabled(),
            )

    async def _read_process_stdout_chunk(
        self,
        process: asyncio.subprocess.Process,
        master_fd: int | None,
        size: int = 4096,
    ) -> bytes:
        if master_fd is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, os.read, master_fd, size)
        assert process.stdout is not None
        return await process.stdout.read(size)
    
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
    
    async def run_simple_prompt(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout: int = 60
    ) -> str:
        """
        Выполнить простой промпт через Cursor CLI без отслеживания файлов,
        без контекста сессии и без стриминга.
        
        Используется для вспомогательных задач (полировка текста и т.п.).
        Использует чтение stdout с idle-детекцией (как process_query),
        чтобы не зависать если cursor-agent не завершается сам.
        
        Args:
            prompt: Текст промпта
            model: Модель (по умолчанию из TRANSCRIPTION_POLISH_MODEL)
            timeout: Таймаут в секундах
        
        Returns:
            str: Ответ модели (пустая строка при ошибке)
        """
        if not self.api_key:
            logger.error("API ключ не установлен для run_simple_prompt")
            return ""
        
        model_to_use = resolve_cursor_cli_model(model or config.TRANSCRIPTION_POLISH_MODEL)

        cmd = ["cursor-agent", "-p", "--force"]
        cmd.extend(["--model", model_to_use])
        
        cmd.append(prompt)
        
        cmd = self._cmd_with_optional_stdbuf(cmd)

        # Подготовить окружение с API ключом и прокси
        env = self._prepare_env()
        
        try:
            logger.info(f"run_simple_prompt: запуск (модель: {model_to_use}, таймаут: {timeout}с)")
            
            # Запускаем из /tmp чтобы не подхватывать .cursor/rules/ из БЗ
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd="/tmp",
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Читаем stdout с idle-детекцией (как в process_query)
            # cursor-agent может не завершаться после вывода ответа
            stdout_chunks = []
            first_chunk_time = None
            last_chunk_time = None
            idle_timeout = 15  # Если stdout замолчал 15с после первых данных — ответ получен
            process_start = time.time()
            
            try:
                while True:
                    # До первого чанка: ждём до общего таймаута
                    # После первого чанка: ждём idle_timeout
                    read_timeout = idle_timeout if first_chunk_time else timeout
                    try:
                        chunk = await asyncio.wait_for(
                            process.stdout.read(4096),
                            timeout=read_timeout
                        )
                    except asyncio.TimeoutError:
                        if first_chunk_time and stdout_chunks:
                            logger.info(
                                f"run_simple_prompt: stdout idle {idle_timeout}с после "
                                f"последнего чанка — завершаем чтение"
                            )
                            break  # Idle timeout — ответ получен
                        else:
                            raise  # Полный таймаут — ни одного чанка
                    
                    if not chunk:
                        break  # EOF — процесс завершился сам
                    
                    decoded = chunk.decode('utf-8', errors='ignore')
                    stdout_chunks.append(decoded)
                    last_chunk_time = time.time()
                    
                    if first_chunk_time is None and decoded.strip():
                        first_chunk_time = time.time()
                        elapsed = first_chunk_time - process_start
                        logger.info(f"run_simple_prompt: первый ответ через {elapsed:.1f}с")
                        
            except asyncio.TimeoutError:
                logger.warning(f"run_simple_prompt: таймаут ({timeout}с), завершаем процесс")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass
                return ""
            
            # Завершить процесс если ещё жив (idle timeout)
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=3.0)
                    except (ProcessLookupError, asyncio.TimeoutError):
                        pass
            
            # Прочитать stderr
            stderr_text = ""
            try:
                stderr_data = await asyncio.wait_for(process.stderr.read(), timeout=3.0)
                stderr_text = stderr_data.decode('utf-8', errors='ignore').strip() if stderr_data else ""
            except (asyncio.TimeoutError, Exception):
                pass
            
            stdout_text = ''.join(stdout_chunks).strip()
            total_time = time.time() - process_start
            
            if not stdout_text and stderr_text:
                logger.warning(
                    f"run_simple_prompt: пустой stdout за {total_time:.1f}с, "
                    f"stderr: {stderr_text[:300]}"
                )
                return ""
            
            if stderr_text:
                logger.debug(f"run_simple_prompt stderr: {stderr_text[:200]}")
            
            logger.info(f"run_simple_prompt: успех ({len(stdout_text)} символов за {total_time:.1f}с)")
            return stdout_text
            
        except FileNotFoundError:
            logger.error("run_simple_prompt: команда 'cursor-agent' не найдена")
            return ""
        except Exception as e:
            logger.error(f"run_simple_prompt: неожиданная ошибка: {e}", exc_info=True)
            return ""
    
    async def create_chat(self) -> Optional[str]:
        """
        Создать новый чат в Cursor CLI, вернуть chatId (UUID)
        
        Returns:
            str: UUID чата или None при ошибке
        """
        env = self._prepare_env()
        
        try:
            process = await asyncio.create_subprocess_exec(
                "cursor-agent", "create-chat",
                cwd=str(self.kb_path),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Актуальные версии cursor-agent печатают UUID в первой строке stdout, но процесс
            # может оставаться живым — communicate() тогда зависает навсегда.
            try:
                first_line = await asyncio.wait_for(process.stdout.readline(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.error("create-chat: таймаут ожидания первой строки stdout (60с)")
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass
                return None

            chat_id = first_line.decode("utf-8", errors="ignore").strip()
            if process.returncode is None:
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=8.0)
                except asyncio.TimeoutError:
                    try:
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except (ProcessLookupError, asyncio.TimeoutError):
                        pass

            stderr_text = ""
            try:
                stderr_data = await asyncio.wait_for(process.stderr.read(), timeout=3.0)
                stderr_text = stderr_data.decode("utf-8", errors="ignore").strip() if stderr_data else ""
            except (asyncio.TimeoutError, Exception):
                pass

            if chat_id:
                logger.info(f"Создан новый чат Cursor CLI: {chat_id}")
                if stderr_text:
                    logger.debug(f"create-chat stderr: {stderr_text[:300]}")
                return chat_id

            logger.warning("cursor-agent create-chat вернул пустой chat id")
            if stderr_text:
                logger.error(f"create-chat stderr: {stderr_text[:500]}")
            return None
        except FileNotFoundError:
            logger.error("Команда 'cursor-agent' не найдена для create-chat")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании чата Cursor CLI: {e}")
            return None
    
    async def _drain_stderr(
        self,
        process: asyncio.subprocess.Process,
        stderr_chunks: List[str],
    ) -> None:
        """Читать stderr параллельно с stdout, чтобы не забить pipe (~64 КБ)."""
        try:
            while True:
                chunk = await process.stderr.read(4096)
                if not chunk:
                    break
                stderr_chunks.append(chunk.decode("utf-8", errors="ignore"))
        except Exception as e:
            logger.debug(f"stderr drain: {e}")

    async def _process_ndjson_line(
        self,
        line: str,
        *,
        accumulator: StreamJsonAccumulator,
        on_chunk: Optional[Callable[[str], Awaitable[None]]],
        on_activity: Optional[Callable[[str], Awaitable[None]]],
    ) -> bool:
        """Returns True if line produced a recognized stream-json event."""
        event = parse_ndjson_line(line)
        if event is None:
            return False
        chunk, activity = accumulator.consume(event)
        if on_chunk and chunk:
            try:
                await on_chunk(chunk)
            except Exception as e:
                logger.debug(f"Ошибка в on_chunk callback: {e}")
        if on_activity and activity:
            try:
                await on_activity(activity)
            except Exception as e:
                logger.debug(f"Ошибка в on_activity callback: {e}")
        return True

    async def _run_stdout_read_loop(
        self,
        *,
        process: asyncio.subprocess.Process,
        master_fd: int | None,
        timeout: int,
        idle_timeout: int,
        cancel_event: Optional[asyncio.Event],
        use_stream_json: bool,
        stream_partial: bool,
        on_chunk: Optional[Callable[[str], Awaitable[None]]],
        on_activity: Optional[Callable[[str], Awaitable[None]]],
        stderr_chunks: List[str],
        process_start_time: float,
    ) -> tuple[
        List[str],
        Optional[float],
        Optional[float],
        bool,
        bool,
        bool,
        Optional[StreamJsonAccumulator],
    ]:
        """
        Read stdout until EOF, idle, cancel, or activity timeout.

        Returns:
            stdout_chunks, first_activity_time, last_activity_time, stdout_eof,
            timed_out_before_activity, user_cancelled, stream_accumulator
        """
        stdout_chunks: List[str] = []
        first_activity_time: Optional[float] = None
        last_activity_time: Optional[float] = None
        stdout_eof = False
        timed_out_before_activity = False
        user_cancelled = False
        stream_accumulator = (
            StreamJsonAccumulator(stream_partial=stream_partial) if use_stream_json else None
        )
        ndjson_buffer = ""

        stderr_task = asyncio.create_task(self._drain_stderr(process, stderr_chunks))

        cancel_task = None
        if cancel_event:
            async def watch_cancel() -> None:
                nonlocal user_cancelled
                await cancel_event.wait()
                user_cancelled = True
                logger.info("Cursor CLI: запрошена отмена пользователем")
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    try:
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                    except (ProcessLookupError, asyncio.TimeoutError):
                        pass

            cancel_task = asyncio.create_task(watch_cancel())

        try:
            while True:
                if first_activity_time:
                    # stream-json: tool calls (e.g. swift test) may run minutes without new events
                    read_timeout = timeout if use_stream_json else idle_timeout
                else:
                    read_timeout = timeout
                try:
                    chunk = await asyncio.wait_for(
                        self._read_process_stdout_chunk(process, master_fd, 4096),
                        timeout=read_timeout,
                    )
                except asyncio.TimeoutError:
                    if first_activity_time and stdout_chunks:
                        idle_elapsed = time.time() - (last_activity_time or first_activity_time)
                        logger.info(
                            "cursor_cli: idle %.1f с после последней активности "
                            "(CURSOR_CLI_IDLE_TIMEOUT=%s) — завершаем чтение",
                            idle_elapsed,
                            idle_timeout,
                        )
                        break
                    timed_out_before_activity = True
                    raise

                if not chunk:
                    stdout_eof = True
                    break

                decoded = chunk.decode("utf-8", errors="ignore")
                stdout_chunks.append(decoded)
                now = time.time()

                if use_stream_json and stream_accumulator is not None:
                    ndjson_buffer += decoded
                    while "\n" in ndjson_buffer:
                        line, ndjson_buffer = ndjson_buffer.split("\n", 1)
                        if not line.strip():
                            continue
                        if await self._process_ndjson_line(
                            line,
                            accumulator=stream_accumulator,
                            on_chunk=on_chunk,
                            on_activity=on_activity,
                        ):
                            if first_activity_time is None:
                                first_activity_time = now
                                logger.info(
                                    "cursor_cli: первое stream-json событие через %.1f с после запуска",
                                    first_activity_time - process_start_time,
                                )
                            last_activity_time = now
                else:
                    if decoded.strip():
                        if first_activity_time is None:
                            first_activity_time = now
                            logger.info(
                                "cursor_cli: первый непустой чанк stdout через %.1f с после запуска",
                                first_activity_time - process_start_time,
                            )
                        last_activity_time = now
                        logger.debug(f"Cursor CLI stdout: {decoded.strip()[:200]}")
                        if on_chunk:
                            try:
                                await on_chunk(decoded)
                            except Exception as e:
                                logger.debug(f"Ошибка в on_chunk callback: {e}")

            if use_stream_json and stream_accumulator is not None and ndjson_buffer.strip():
                if await self._process_ndjson_line(
                    ndjson_buffer,
                    accumulator=stream_accumulator,
                    on_chunk=on_chunk,
                    on_activity=on_activity,
                ):
                    last_activity_time = time.time()
                    if first_activity_time is None:
                        first_activity_time = last_activity_time

        except asyncio.TimeoutError:
            pass
        finally:
            if cancel_task:
                cancel_task.cancel()
                try:
                    await cancel_task
                except asyncio.CancelledError:
                    pass
            try:
                await asyncio.wait_for(stderr_task, timeout=8.0)
            except Exception:
                if not stderr_task.done():
                    stderr_task.cancel()

        if user_cancelled:
            return (
                stdout_chunks,
                first_activity_time,
                last_activity_time,
                stdout_eof,
                timed_out_before_activity,
                True,
                stream_accumulator,
            )

        return (
            stdout_chunks,
            first_activity_time,
            last_activity_time,
            stdout_eof,
            timed_out_before_activity,
            False,
            stream_accumulator,
        )
    
    async def process_query(
        self,
        query: str,
        session_id: Optional[int] = None,
        model: Optional[str] = None,
        session_messages: Optional[List[Dict[str, Any]]] = None,
        attached_files: Optional[List[Path]] = None,
        cursor_chat_id: Optional[str] = None,
        on_chunk: Optional[Callable[[str], Awaitable[None]]] = None,
        on_activity: Optional[Callable[[str], Awaitable[None]]] = None,
        cancel_event: Optional[asyncio.Event] = None,
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
            on_chunk: Async callback для стриминга чанков stdout (опционально)
            on_activity: Async callback для прогресса stream-json (tool_call и т.д.)
            cancel_event: при set() процесс cursor-agent принудительно завершается (отмена пользователем)
        
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
        
        model_to_use = resolve_cursor_cli_model(model or self.model)
        cmd.extend(["--model", model_to_use])
        if (model or self.model or "").strip().lower() in ("", "auto", "default"):
            logger.debug("CURSOR_MODEL=auto → cursor-agent --model auto (пул Auto)")
        
        # Дополнительные флаги для оптимизации (если доступны)
        # Можно добавить через переменные окружения для экспериментов
        additional_flags = os.getenv("CURSOR_CLI_EXTRA_FLAGS", "").strip()
        if additional_flags:
            cmd.extend(additional_flags.split())

        self._append_output_format_flags(cmd)
        
        # Добавить полный запрос
        cmd.append(full_query)
        
        # Подготовить окружение с API ключом и прокси
        env = self._prepare_env()
        
        # Таймаут из конфига (по умолчанию 10 минут)
        timeout = int(os.getenv("CURSOR_CLI_TIMEOUT", "600"))
        use_stream_json = self._cursor_output_format() == "stream-json"
        stream_partial = self._stream_partial_output_enabled()
        
        master_fd: int | None = None
        try:
            # Выполнить команду в директории базы знаний
            logger.info(f"Выполнение команды: {' '.join(cmd)}")
            logger.info(f"Рабочая директория: {self.kb_path}")
            logger.info(f"Таймаут: {timeout} секунд")
            logger.debug(f"API ключ установлен: {'Да' if self.api_key else 'Нет'}")
            
            cmd = self._cmd_with_optional_stdbuf(cmd)

            slave_fd: int | None = None
            stdout_target: int | asyncio.subprocess.PIPE = asyncio.subprocess.PIPE
            if self._use_pty_for_stdout():
                master_fd, slave_fd = pty.openpty()
                stdout_target = slave_fd
                logger.debug("Cursor CLI: stdout через PTY (macOS line streaming)")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(self.kb_path),
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=stdout_target,
                stderr=asyncio.subprocess.PIPE,
            )
            if slave_fd is not None:
                os.close(slave_fd)
            
            logger.info(f"Процесс Cursor CLI запущен (PID: {process.pid})")

            process_start_time = time.time()
            idle_timeout = int(os.getenv("CURSOR_CLI_IDLE_TIMEOUT", "30"))
            stderr_chunks: List[str] = []

            (
                stdout_chunks,
                first_activity_time,
                _last_activity_time,
                stdout_eof,
                timed_out_before_activity,
                user_cancelled,
                stream_accumulator,
            ) = await self._run_stdout_read_loop(
                process=process,
                master_fd=master_fd,
                timeout=timeout,
                idle_timeout=idle_timeout,
                cancel_event=cancel_event,
                use_stream_json=use_stream_json,
                stream_partial=stream_partial,
                on_chunk=on_chunk,
                on_activity=on_activity,
                stderr_chunks=stderr_chunks,
                process_start_time=process_start_time,
            )

            if user_cancelled:
                return CURSOR_QUERY_CANCELLED_MESSAGE, []

            if timed_out_before_activity:
                logger.error(
                    "cursor_cli: таймаут до первой активности — %s с (CURSOR_CLI_TIMEOUT); "
                    "завершаем процесс (PID=%s)",
                    timeout,
                    getattr(process, "pid", None),
                )
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    pass
                stderr_text = "".join(stderr_chunks)
                if stderr_text:
                    logger.error(
                        "cursor_cli: stderr (хвост, таймаут до активности): %s",
                        stderr_text[-2000:],
                    )
                return CURSOR_USER_TIMEOUT_FIRST_CHUNK, []

            # === Фаза 2: Завершаем процесс и дочитываем буфер ===
            process_killed_early = False
            
            if stdout_eof:
                # Процесс завершился сам — все данные уже получены
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                logger.info(f"Cursor CLI: процесс завершился естественно")
            else:
                # Idle timeout — процесс ещё жив, но stdout замолчал
                # Отправляем SIGTERM для корректного завершения (flush буферов)
                if process.returncode is None:
                    logger.info("Cursor CLI: stdout idle, отправляем SIGTERM для сброса буферов...")
                    try:
                        process.terminate()  # SIGTERM — позволяет процессу сбросить буферы
                    except ProcessLookupError:
                        pass
                    
                    # Ждём завершения (SIGTERM обычно вызывает flush stdout)
                    try:
                        await asyncio.wait_for(process.wait(), timeout=10.0)
                        logger.info(f"Cursor CLI: процесс завершился по SIGTERM")
                    except asyncio.TimeoutError:
                        # SIGTERM не помог — SIGKILL
                        logger.warning("Cursor CLI: SIGTERM не помог за 10с, отправляем SIGKILL...")
                        try:
                            process.kill()
                            process_killed_early = True
                            await asyncio.wait_for(process.wait(), timeout=5.0)
                        except (ProcessLookupError, asyncio.TimeoutError):
                            pass
                
                # Дочитать оставшиеся данные из stdout (сброшенные при завершении)
                try:
                    if master_fd is not None:
                        while True:
                            remaining = await asyncio.wait_for(
                                self._read_process_stdout_chunk(process, master_fd, 4096),
                                timeout=5.0,
                            )
                            if not remaining:
                                break
                            decoded = remaining.decode("utf-8", errors="ignore")
                            stdout_chunks.append(decoded)
                            if on_chunk and decoded.strip():
                                try:
                                    await on_chunk(decoded)
                                except Exception as e:
                                    logger.debug(f"Ошибка в on_chunk callback: {e}")
                    elif process.stdout is not None:
                        remaining = await asyncio.wait_for(process.stdout.read(), timeout=5.0)
                        if remaining:
                            decoded = remaining.decode('utf-8', errors='ignore')
                            stdout_chunks.append(decoded)
                            logger.info(
                                f"Cursor CLI: дочитано ещё {len(remaining)} байт из stdout "
                                f"после завершения процесса"
                            )
                except (asyncio.TimeoutError, Exception) as e:
                    logger.debug(f"Cursor CLI: не удалось дочитать stdout: {e}")
            
            # === Фаза 3: Логирование и обработка результата ===
            returncode = process.returncode
            total_process_time = time.time() - process_start_time
            
            if process_killed_early:
                logger.info(
                    f"Cursor CLI процесс завершён принудительно (SIGKILL) за {total_process_time:.1f}с"
                )
            elif not stdout_eof:
                logger.info(
                    f"Cursor CLI процесс завершён (SIGTERM) за {total_process_time:.1f}с"
                )
            else:
                logger.info(f"Cursor CLI процесс завершён за {total_process_time:.1f}с (код: {returncode})")
            
            if first_activity_time:
                response_to_done = time.time() - first_activity_time
                logger.info(f"Cursor CLI: от первой активности до готовности: {response_to_done:.1f}с")
            
            stdout_text = "".join(stdout_chunks)
            stderr_text = "".join(stderr_chunks)
            
            if stdout_text:
                logger.debug(f"Cursor CLI stdout ({len(stdout_text)} символов): {stdout_text[:1000]}")
            if stderr_text:
                logger.info(f"Cursor CLI stderr: {stderr_text[:1000]}")
            
            if returncode != 0 and not process_killed_early and stdout_eof:
                logger.error(
                    "cursor_cli: процесс завершился с кодом %s; stderr (хвост): %s",
                    returncode,
                    (stderr_text[-2000:] if stderr_text else "(пусто)"),
                )
                stderr_l = (stderr_text or "").lower()
                if "cannot use this model" in stderr_l or (
                    "available models:" in stderr_l
                    and stderr_l.rstrip().endswith("available models:")
                ):
                    return CURSOR_USER_MODEL_UNAVAILABLE, []
                return CURSOR_USER_PROCESS_FAILED, []
            
            if stream_accumulator is not None:
                response = strip_terminal_escape_sequences(stream_accumulator.final_response().strip())
            else:
                response = strip_terminal_escape_sequences(stdout_text.strip())
            
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
            logger.error("Неожиданная ошибка при вызове Cursor CLI: %s", e, exc_info=True)
            return (
                "❌ Не удалось выполнить запрос. Попробуйте позже или обратитесь к администратору.",
                [],
            )
        finally:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except OSError:
                    pass
    
    async def _save_file_states(self) -> Dict[str, Dict[str, Any]]:
        """
        Сохранить снимок файловой системы для отслеживания изменений.
        
        Сканирует файлы рекурсивно и сохраняет путь → {mtime, size}.
        Не использует git — работает в любом окружении (Docker и т.д.).
        
        Returns:
            Dict[str, Dict]: Словарь {относительный_путь: {mtime, size}}
        """
        file_states = {}
        try:
            for item in self.kb_path.rglob('*'):
                if item.is_file():
                    # Пропустить служебные файлы и директории
                    rel_path = str(item.relative_to(self.kb_path))
                    if is_excluded_sync_path(rel_path, config.SYNC_EXCLUDE_PATTERNS):
                        continue
                    
                    try:
                        stat = item.stat()
                        file_states[rel_path] = {
                            'mtime': stat.st_mtime,
                            'size': stat.st_size,
                        }
                    except OSError:
                        pass
            
            logger.debug(f"Снимок файловой системы: {len(file_states)} файлов")
        except Exception as e:
            logger.warning(f"Не удалось сохранить состояние файлов: {e}")
        
        return file_states
    
    async def _get_file_changes(self, file_states_before: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Получить список изменённых файлов, сравнивая снимки файловой системы.
        
        Обнаруживает:
        - Новые файлы (есть сейчас, не было до)
        - Изменённые файлы (mtime или size изменились)
        - Удалённые файлы (были до, нет сейчас)
        
        Args:
            file_states_before: Снимок файловой системы ДО выполнения запроса
        
        Returns:
            List[Dict]: Список изменений [{path, type, old_content, new_content}]
        """
        changes = []
        
        try:
            # Сделать снимок "после"
            file_states_after = await self._save_file_states()
            
            paths_before = set(file_states_before.keys())
            paths_after = set(file_states_after.keys())
            
            # Новые файлы (created)
            new_files = paths_after - paths_before
            for rel_path in new_files:
                full_path = self.kb_path / rel_path
                try:
                    new_content = full_path.read_text(encoding='utf-8', errors='ignore')
                    changes.append({
                        "path": rel_path,
                        "type": "created",
                        "old_content": None,
                        "new_content": new_content
                    })
                    logger.info(f"Обнаружен новый файл: {rel_path}")
                except Exception as e:
                    logger.debug(f"Ошибка при чтении нового файла {rel_path}: {e}")
            
            # Изменённые файлы (modified) — mtime или size изменились
            common_files = paths_before & paths_after
            for rel_path in common_files:
                before = file_states_before[rel_path]
                after = file_states_after[rel_path]
                
                if before['mtime'] != after['mtime'] or before['size'] != after['size']:
                    full_path = self.kb_path / rel_path
                    try:
                        new_content = full_path.read_text(encoding='utf-8', errors='ignore')
                        changes.append({
                            "path": rel_path,
                            "type": "modified",
                            "old_content": None,  # Не храним полное содержимое до
                            "new_content": new_content
                        })
                        logger.info(f"Обнаружен изменённый файл: {rel_path}")
                    except Exception as e:
                        logger.debug(f"Ошибка при чтении изменённого файла {rel_path}: {e}")
            
            # Удалённые файлы (deleted)
            deleted_files = paths_before - paths_after
            for rel_path in deleted_files:
                changes.append({
                    "path": rel_path,
                    "type": "deleted",
                    "old_content": None,
                    "new_content": None
                })
                logger.info(f"Обнаружен удалённый файл: {rel_path}")
            
            if changes:
                logger.info(
                    f"Обнаружено изменений: {len(changes)} "
                    f"(новых: {len(new_files)}, изменённых: {len(changes) - len(new_files) - len(deleted_files)}, "
                    f"удалённых: {len(deleted_files)})"
                )
            else:
                logger.debug("Изменений файлов не обнаружено")
                
        except Exception as e:
            logger.warning(f"Ошибка при получении изменений файлов: {e}")

        filtered = filter_trackable_changes(changes, config.SYNC_EXCLUDE_PATTERNS)
        if len(filtered) != len(changes):
            logger.info(
                "Отфильтровано служебных изменений: %d → %d",
                len(changes),
                len(filtered),
            )
        return filtered
    
    async def get_file_changes(self) -> List[Dict[str, Any]]:
        """Получить список изменённых файлов (сравнение с пустым состоянием)"""
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

