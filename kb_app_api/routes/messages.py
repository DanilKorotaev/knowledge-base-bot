from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import config

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.message_enrichment import enrich_session_messages
from kb_app_api.session_access import parse_session_id, require_session_for_user
from kb_app_api.voice_attachments import attach_voice_to_last_user_message, voice_upload_path
from services.query_processing_service import QueryProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["messages"])

_DEFAULT_ATTACH_PROMPT = (
    "Пользователь прикрепил файл. Проанализируй его в контексте базы знаний и ответь."
)


def _safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    if not base or base in (".", ".."):
        base = "upload.bin"
    clean = re.sub(r"[^\w.\-]", "_", base)
    return (clean[:200] or "upload.bin")


class PostMessageBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=32000)
    use_knowledge_base: bool = True


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    limit: int = 20,
    before: str | None = None,
) -> dict[str, Any]:
    """
    Пагинация «снизу вверх» для iOS-чата.
    Без `before` — последние `limit` сообщений (хронологический порядок).
    С `before={message_id}` — ещё `limit` сообщений старше указанного id.
    """
    if limit < 1 or limit > 100:
        raise APIError("validation_error", "limit должен быть 1…100", detail="limit")

    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    before_id: int | None = None
    if before is not None and before.strip():
        try:
            before_id = int(before.strip())
        except ValueError as e:
            raise APIError("validation_error", "before должен быть id сообщения", detail="before") from e

    from utils.db_helpers import get_db

    db = await get_db()
    chunk, total, has_more_older = await db.get_session_messages_window(
        sid, limit=limit, before_id=before_id
    )
    return {
        "messages": await enrich_session_messages(sid, chunk),
        "total": total,
        "has_more_older": has_more_older,
    }


@router.post("/{session_id}/messages")
async def post_message(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: PostMessageBody,
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    wants_sse = accept and "text/event-stream" in accept.lower()
    tid = int(user["telegram_id"])

    if wants_sse:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        err_holder: list[BaseException | None] = [None]

        async def on_chunk(chunk: str) -> None:
            await queue.put(chunk)

        async def run_pipeline() -> None:
            try:
                qps = QueryProcessingService()
                await qps.process_query_for_api(
                    body.content,
                    sid,
                    tid,
                    use_knowledge_base=body.use_knowledge_base,
                    on_chunk=on_chunk,
                )
            except BaseException as e:
                err_holder[0] = e
            finally:
                await queue.put(None)

        async def gen():
            task = asyncio.create_task(run_pipeline())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield f"data: {json.dumps({'delta': item}, ensure_ascii=False)}\n\n"
                await task
                ex = err_holder[0]
                if ex:
                    msg = str(ex)
                    yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(gen(), media_type="text/event-stream")

    try:
        qps = QueryProcessingService()
        await qps.process_query_for_api(
            body.content,
            sid,
            tid,
            use_knowledge_base=body.use_knowledge_base,
        )
    except RuntimeError as e:
        raise APIError("processing_error", str(e), status_code=500) from e

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    payload = {"messages": await enrich_session_messages(sid, all_msgs)}
    return JSONResponse(content=payload, status_code=201)


@router.post("/{session_id}/attachments")
async def post_attachment(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    file: UploadFile = File(...),
    use_knowledge_base: str = Form(default="true"),
    message: str | None = Form(default=None),
) -> JSONResponse:
    """
    multipart: `file`, `use_knowledge_base`, опционально `message` — текст запроса вместо текста по умолчанию.
    """
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])
    tid = int(user["telegram_id"])
    use_kb = str(use_knowledge_base).lower() in ("1", "true", "yes", "on")

    data = await file.read()
    if not data:
        raise APIError("validation_error", "Пустой файл", detail="file")

    safe = _safe_filename(file.filename)
    kb_root = Path(config.LOCAL_KB_PATH)
    kb_root.mkdir(parents=True, exist_ok=True)
    upload_root = kb_root / ".kb_app_api_uploads" / str(sid)
    upload_root.mkdir(parents=True, exist_ok=True)
    dest = upload_root / f"{uuid.uuid4().hex[:10]}_{safe}"
    dest.write_bytes(data)

    query_text = (message or "").strip() or _DEFAULT_ATTACH_PROMPT

    try:
        qps = QueryProcessingService()
        await qps.process_query_for_api(
            query_text,
            sid,
            tid,
            use_knowledge_base=use_kb,
            attached_files=[dest],
        )
    except RuntimeError as e:
        dest.unlink(missing_ok=True)
        raise APIError("processing_error", str(e), status_code=500) from e

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    last_user = None
    for m in reversed(all_msgs):
        if m.get("role") == "user":
            last_user = m
            break
    if last_user:
        mime, _ = mimetypes.guess_type(safe)
        ftype = "photo" if mime and mime.startswith("image/") else "document"
        try:
            await db.add_attachment(
                session_id=sid,
                message_id=last_user["id"],
                file_type=ftype,
                file_id=f"kb_app_api:{uuid.uuid4().hex}",
                file_path=str(dest),
                file_name=safe,
                file_size=len(data),
            )
        except Exception as e:
            logger.warning("Не удалось сохранить метаданные вложения: %s", e)

    payload = {"messages": await enrich_session_messages(sid, await db.get_session_messages(sid))}
    return JSONResponse(content=payload, status_code=201)


@router.post("/{session_id}/messages/voice")
async def post_voice_message(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    audio: UploadFile = File(...),
    content: str = Form(...),
    use_knowledge_base: str = Form(default="true"),
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """
    Отредактированная транскрипция (`content`) + файл `audio` → пайплайн как у текста,
    затем voice attachment и transcription в БД (как в Telegram-боте).
    """
    text = (content or "").strip()
    if not text:
        raise APIError("validation_error", "Нужно непустое поле content", detail="content")

    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    data = await audio.read()
    if not data:
        raise APIError("validation_error", "Пустой файл audio", detail="audio")

    safe = _safe_filename(audio.filename)
    if not safe.lower().endswith((".m4a", ".mp4", ".ogg", ".wav", ".webm", ".mp3")):
        base = safe.rsplit(".", 1)[0] if "." in safe else safe
        safe = f"{base}.m4a"

    dest = voice_upload_path(sid, safe)
    dest.write_bytes(data)
    file_size = len(data)

    use_kb = str(use_knowledge_base).lower() in ("1", "true", "yes", "on")
    tid = int(user["telegram_id"])
    wants_sse = accept and "text/event-stream" in accept.lower()

    async def persist_voice() -> None:
        await attach_voice_to_last_user_message(sid, dest, safe, file_size, text)

    if wants_sse:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        err_holder: list[BaseException | None] = [None]

        async def on_chunk(chunk: str) -> None:
            await queue.put(chunk)

        async def run_pipeline() -> None:
            try:
                qps = QueryProcessingService()
                await qps.process_query_for_api(
                    text,
                    sid,
                    tid,
                    use_knowledge_base=use_kb,
                    on_chunk=on_chunk,
                )
                await persist_voice()
            except BaseException as e:
                err_holder[0] = e
                dest.unlink(missing_ok=True)
            finally:
                await queue.put(None)

        async def gen():
            task = asyncio.create_task(run_pipeline())
            try:
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield f"data: {json.dumps({'delta': item}, ensure_ascii=False)}\n\n"
                await task
                ex = err_holder[0]
                if ex:
                    msg = str(ex)
                    yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            finally:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

        return StreamingResponse(gen(), media_type="text/event-stream")

    try:
        qps = QueryProcessingService()
        await qps.process_query_for_api(
            text,
            sid,
            tid,
            use_knowledge_base=use_kb,
        )
        await persist_voice()
    except RuntimeError as e:
        dest.unlink(missing_ok=True)
        raise APIError("processing_error", str(e), status_code=500) from e
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    payload = {"messages": await enrich_session_messages(sid, all_msgs)}
    return JSONResponse(content=payload, status_code=201)
