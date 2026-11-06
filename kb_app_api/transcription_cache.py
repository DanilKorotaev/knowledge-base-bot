"""In-process idempotent transcription cache keyed by (user_id, client_transcription_id)."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
DEFAULT_TTL_SEC = 3600.0


def validate_client_transcription_id(raw: str | None) -> Optional[str]:
    text = (raw or "").strip()
    if not text:
        return None
    if not _CLIENT_ID_RE.match(text):
        raise ValueError("invalid client_transcription_id")
    return text


@dataclass
class _Entry:
    status: str  # pending | ready | failed
    text: Optional[str] = None
    error: Optional[BaseException] = None
    future: Optional[asyncio.Future[str]] = None
    updated_at: float = field(default_factory=time.time)
    whisper_runs: int = 0


class TranscriptionCache:
    def __init__(self, *, ttl_sec: float = DEFAULT_TTL_SEC) -> None:
        self._ttl = ttl_sec
        self._lock = asyncio.Lock()
        self._entries: dict[tuple[int, str], _Entry] = {}

    def stats_for(self, user_id: int, client_id: str) -> dict[str, object]:
        ent = self._entries.get((user_id, client_id))
        if not ent:
            return {"status": "miss"}
        return {
            "status": ent.status,
            "whisper_runs": ent.whisper_runs,
            "has_text": bool(ent.text),
        }

    async def get_or_run(
        self,
        user_id: int,
        client_id: str,
        factory: Callable[[], Awaitable[str]],
    ) -> str:
        """Return cached ready text, join in-flight work, or start a new Whisper run."""
        key = (user_id, client_id)
        async with self._lock:
            self._purge_locked()
            ent = self._entries.get(key)
            if ent is not None and ent.status == "ready" and ent.text is not None:
                logger.info(
                    "transcription cache hit user=%s id=%s whisper_runs=%s",
                    user_id,
                    client_id,
                    ent.whisper_runs,
                )
                return ent.text
            if (
                ent is not None
                and ent.status == "pending"
                and ent.future is not None
                and not ent.future.done()
            ):
                logger.info(
                    "transcription cache coalesce user=%s id=%s",
                    user_id,
                    client_id,
                )
                fut = ent.future
            else:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                self._entries[key] = _Entry(status="pending", future=fut, updated_at=time.time())
                loop.create_task(self._run(key, fut, factory))
                fut = self._entries[key].future
                assert fut is not None
        return await asyncio.shield(fut)

    async def _run(
        self,
        key: tuple[int, str],
        fut: asyncio.Future[str],
        factory: Callable[[], Awaitable[str]],
    ) -> None:
        user_id, client_id = key
        try:
            text = await factory()
            async with self._lock:
                ent = self._entries.get(key)
                runs = (ent.whisper_runs + 1) if ent else 1
                self._entries[key] = _Entry(
                    status="ready",
                    text=text,
                    updated_at=time.time(),
                    whisper_runs=runs,
                )
            if not fut.done():
                fut.set_result(text)
            logger.info(
                "transcription cache ready user=%s id=%s whisper_runs=%s",
                user_id,
                client_id,
                runs,
            )
        except BaseException as exc:
            async with self._lock:
                ent = self._entries.get(key)
                runs = (ent.whisper_runs + 1) if ent else 1
                # Do not keep failed forever — next call may retry Whisper.
                self._entries.pop(key, None)
            if not fut.done():
                fut.set_exception(exc)
            logger.info(
                "transcription cache failed user=%s id=%s whisper_runs=%s err=%s",
                user_id,
                client_id,
                runs,
                type(exc).__name__,
            )

    def _purge_locked(self) -> None:
        now = time.time()
        dead = [
            key
            for key, ent in self._entries.items()
            if ent.status == "ready" and (now - ent.updated_at) > self._ttl
        ]
        for key in dead:
            self._entries.pop(key, None)


# Process-wide cache for the API worker.
transcription_cache = TranscriptionCache()
