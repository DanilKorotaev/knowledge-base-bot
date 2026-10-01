"""Generate a short display title for a chat session after the first Q&A."""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from config import config

logger = logging.getLogger(__name__)

_PLACEHOLDER_TITLES = frozenset(
    {
        "",
        "новый чат",
        "new chat",
        "new session",
    }
)
_SESSION_NUM_RE = re.compile(r"^session\s+\d+$", re.I)
_WHITESPACE_RE = re.compile(r"\s+")


def is_unset_display_title(display_title: Optional[str], session_id: int | None = None) -> bool:
    """True when auto-title is allowed (NULL / placeholder / Session N)."""
    if display_title is None:
        return True
    text = str(display_title).strip()
    if not text:
        return True
    if text.casefold() in _PLACEHOLDER_TITLES:
        return True
    if _SESSION_NUM_RE.match(text):
        return True
    if session_id is not None and text.casefold() == f"session {session_id}".casefold():
        return True
    return False


def fallback_title_from_query(query: str, *, max_len: int = 72) -> str:
    text = _WHITESPACE_RE.sub(" ", (query or "").strip())
    if not text:
        return "Новый чат"
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1].rsplit(" ", 1)[0] or text[: max_len - 1]
    return cut.rstrip(".,;:") + "…"


def _clean_model_title(raw: str, *, max_len: int = 80) -> str:
    text = (raw or "").strip().strip("\"'`")
    text = text.splitlines()[0].strip() if text else ""
    text = _WHITESPACE_RE.sub(" ", text)
    # Drop leading labels like "Title:" / «Заголовок:»
    text = re.sub(r"^(title|заголовок)\s*[:：\-—]\s*", "", text, flags=re.I)
    if len(text) > max_len:
        text = (text[: max_len - 1].rsplit(" ", 1)[0] or text[: max_len - 1]) + "…"
    return text


class SessionTitleService:
    """One-shot title fill when display_title is still unset."""

    def __init__(self, cursor_service: Any | None = None) -> None:
        self._cursor = cursor_service

    def _get_cursor(self) -> Any:
        if self._cursor is not None:
            return self._cursor
        from services.cursor_cli_service import CursorCLIService

        self._cursor = CursorCLIService()
        return self._cursor

    async def maybe_set_title_after_first_reply(
        self,
        db: Any,
        session_id: int,
        *,
        user_query: str,
        assistant_reply: str = "",
    ) -> Optional[str]:
        """
        If the session has no real title yet, generate one and persist.
        Returns the new title, or None when skipped / failed without fallback write.
        """
        if not getattr(config, "SESSION_TITLE_ENABLED", True):
            return None
        session = await db.get_session(session_id)
        if not session:
            return None
        if not is_unset_display_title(session.get("display_title"), session_id):
            return None

        title = await self.generate_title(user_query, assistant_reply)
        if not title:
            title = fallback_title_from_query(user_query)
        # Re-check race: user may have renamed meanwhile.
        session2 = await db.get_session(session_id)
        if session2 and not is_unset_display_title(session2.get("display_title"), session_id):
            return None
        await db.update_session(session_id, display_title=title)
        logger.info("session_title set session_id=%s title=%r", session_id, title)
        return title

    async def generate_title(self, user_query: str, assistant_reply: str = "") -> Optional[str]:
        prompt = self._build_prompt(user_query, assistant_reply)
        try:
            cursor = self._get_cursor()
            model = getattr(config, "SESSION_TITLE_MODEL", None) or config.TRANSCRIPTION_POLISH_MODEL
            timeout = float(getattr(config, "SESSION_TITLE_TIMEOUT_SEC", 45) or 45)
            raw = await cursor.run_simple_prompt(prompt, model=model, timeout=timeout)
            cleaned = _clean_model_title(raw or "")
            if cleaned:
                return cleaned
        except Exception as exc:
            logger.warning("session_title LLM failed: %s", exc, exc_info=True)
        return None

    @staticmethod
    def _build_prompt(user_query: str, assistant_reply: str) -> str:
        user = (user_query or "").strip()[:1200]
        reply = (assistant_reply or "").strip()[:600]
        parts = [
            "Придумай короткий заголовок чата (3–8 слов) по смыслу диалога.",
            "Язык заголовка = язык вопроса пользователя.",
            "Без кавычек, без точки в конце, без префикса «Заголовок:».",
            "Только одна строка — сам заголовок.",
            "",
            f"Вопрос пользователя:\n{user}",
        ]
        if reply:
            parts.extend(["", f"Краткий ответ ассистента (контекст):\n{reply}"])
        return "\n".join(parts)
