from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.serializers import message_to_kb
from kb_app_api.session_access import parse_session_id, require_session_for_user
from services.openai_service import OpenAIService
from services.query_processing_service import QueryProcessingService
from services.transcription_service import TranscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["voice"])


@router.post("/voice")
async def voice_query(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    audio: UploadFile | None = File(default=None),
    session_id: str = Form(default=""),
    use_knowledge_base: str = Form(default="true"),
    transcription_hint: str | None = Form(default=None),
) -> dict[str, Any]:
    """
    Multipart: поле `audio` (как в Telegram — Whisper), либо текст из `transcription_hint`.
    Дальше — тот же пайплайн, что у `POST .../messages` (Cursor / режим без KB).
    """
    if not session_id.strip():
        raise APIError("validation_error", "Нужно поле session_id", detail="session_id")

    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    use_kb = str(use_knowledge_base).lower() in ("1", "true", "yes", "on")
    tid = int(user["telegram_id"])

    text_for_pipeline: str
    transcription_out: str

    if audio is not None:
        data = await audio.read()
    else:
        data = b""

    if len(data) > 0:
        suf = Path(audio.filename or "audio.m4a").suffix if audio else ".m4a"
        if not suf or len(suf) > 8:
            suf = ".m4a"
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suf, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            openai = OpenAIService()
            ts = TranscriptionService(openai)
            result = await ts.transcribe(tmp_path)
            raw = (result.get("text") or "").strip()
            language = result.get("language")
            if not raw:
                raise APIError(
                    "transcription_empty",
                    "Не удалось распознать речь",
                    status_code=422,
                )
            text_for_pipeline = await TranscriptionService.polish_transcription_simple(raw, language)
            transcription_out = text_for_pipeline
        except APIError:
            raise
        except Exception as e:
            logger.exception("Whisper / полировка (KB App API voice): %s", e)
            raise APIError(
                "transcription_failed",
                "Ошибка распознавания речи",
                status_code=502,
                detail=str(e),
            ) from e
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)
    elif transcription_hint and transcription_hint.strip():
        text_for_pipeline = transcription_hint.strip()
        transcription_out = text_for_pipeline
    else:
        raise APIError(
            "validation_error",
            "Нужен непустой файл audio или поле transcription_hint",
            detail="audio|transcription_hint",
        )

    try:
        qps = QueryProcessingService()
        await qps.process_query_for_api(
            text_for_pipeline,
            sid,
            tid,
            use_knowledge_base=use_kb,
        )
    except RuntimeError as e:
        raise APIError("processing_error", str(e), status_code=500) from e

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    return {
        "messages": [message_to_kb(m) for m in all_msgs],
        "transcription": transcription_out,
    }
