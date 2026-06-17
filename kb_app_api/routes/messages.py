from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Header, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from config import config

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.message_enrichment import enrich_session_messages
from kb_app_api.session_access import parse_session_id, require_session_for_user
from kb_app_api.voice_attachments import attach_voice_to_message, attach_voice_to_last_user_message, voice_upload_path
from services.query_processing_service import QueryProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["messages"])

# Disable nginx/proxy buffering for SSE (see kbapp nginx `proxy_buffering off`).
SSE_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

# When Cursor CLI dumps stdout in one block, split for visible typing in clients.
_SSE_PIECE_MAX = int(os.getenv("STREAM_SSE_PIECE_CHARS", "48"))
_SSE_PIECE_DELAY_SEC = float(os.getenv("STREAM_SSE_PIECE_DELAY_MS", "18")) / 1000.0


def _iter_sse_delta_pieces(text: str, *, max_piece: int = _SSE_PIECE_MAX) -> list[str]:
    if not text:
        return []
    if len(text) <= max_piece:
        return [text]
    pieces: list[str] = []
    for line in text.splitlines(keepends=True):
        if len(line) <= max_piece:
            pieces.append(line)
            continue
        start = 0
        while start < len(line):
            pieces.append(line[start : start + max_piece])
            start += max_piece
    return pieces or [text]


async def _yield_sse_deltas(item: str):
    pieces = _iter_sse_delta_pieces(item)
    for index, piece in enumerate(pieces):
        yield f"data: {json.dumps({'delta': piece}, ensure_ascii=False)}\n\n"
        if len(pieces) > 1 and index + 1 < len(pieces) and _SSE_PIECE_DELAY_SEC > 0:
            await asyncio.sleep(_SSE_PIECE_DELAY_SEC)
        else:
            await asyncio.sleep(0)


async def _stream_assistant_sse(
    *,
    session_id: int,
    queue: asyncio.Queue[str | None],
    err_holder: list[BaseException | None],
    run_pipeline: Callable[[], Awaitable[None]],
) -> AsyncIterator[str]:
    """
    Stream assistant deltas to the client.

    If the HTTP/SSE client disconnects (app backgrounded, chat closed), the pipeline
    task keeps running so Cursor can finish and the reply is persisted for later GET.
    """
    yield f"data: {json.dumps({'status': 'processing'}, ensure_ascii=False)}\n\n"
    task = asyncio.create_task(run_pipeline())
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            async for event in _yield_sse_deltas(item):
                yield event
        await task
        ex = err_holder[0]
        if ex:
            msg = str(ex)
            yield f"data: {json.dumps({'error': msg}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except asyncio.CancelledError:
        if not task.done():
            logger.info(
                "SSE client disconnected (session_id=%s); query pipeline continues in background",
                session_id,
            )
        raise

_DEFAULT_ATTACH_PROMPT = (
    "Пользователь прикрепил файл. Проанализируй его в контексте базы знаний и ответь."
)


def _safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    if not base or base in (".", ".."):
        base = "upload.bin"
    clean = re.sub(r"[^\w.\-]", "_", base)
    return (clean[:200] or "upload.bin")


def _parse_use_kb(value: str) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on")


def _session_upload_root(session_id: int) -> Path:
    kb_root = Path(config.LOCAL_KB_PATH)
    kb_root.mkdir(parents=True, exist_ok=True)
    upload_root = kb_root / ".kb_app_api_uploads" / str(session_id)
    upload_root.mkdir(parents=True, exist_ok=True)
    return upload_root


async def _attach_file_to_message(
    session_id: int,
    message_id: int,
    dest: Path,
    safe_filename: str,
    file_size: int,
) -> None:
    from utils.db_helpers import get_db

    db = await get_db()
    mime, _ = mimetypes.guess_type(safe_filename)
    ftype = "photo" if mime and mime.startswith("image/") else "document"
    try:
        await db.add_attachment(
            session_id=session_id,
            message_id=message_id,
            file_type=ftype,
            file_id=f"kb_app_api:{uuid.uuid4().hex}",
            file_path=str(dest),
            file_name=safe_filename,
            file_size=file_size,
        )
    except Exception as e:
        logger.warning("Не удалось сохранить метаданные вложения: %s", e)


def _parse_audio_transcriptions(raw: str | None, audio_count: int) -> list[str]:
    if audio_count == 0:
        return []
    if not raw or not raw.strip():
        return [""] * audio_count
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise APIError(
            "validation_error",
            "audio_transcriptions должен быть JSON-массивом строк",
            detail="audio_transcriptions",
        ) from e
    if not isinstance(parsed, list):
        raise APIError(
            "validation_error",
            "audio_transcriptions должен быть JSON-массивом строк",
            detail="audio_transcriptions",
        )
    result = [str(item) if item is not None else "" for item in parsed]
    if len(result) != audio_count:
        raise APIError(
            "validation_error",
            f"Число транскрипций ({len(result)}) не совпадает с числом audio ({audio_count})",
            detail="audio_transcriptions",
        )
    return result


def _compose_query_text(content: str, file_count: int, transcriptions: list[str]) -> str:
    trimmed = (content or "").strip()
    if trimmed:
        return trimmed
    if file_count > 0:
        return _DEFAULT_ATTACH_PROMPT
    voice_text = " ".join(part.strip() for part in transcriptions if part.strip())
    if voice_text:
        return voice_text
    return _DEFAULT_ATTACH_PROMPT


async def _persist_compose_uploads(
    session_id: int,
    message_id: int,
    file_uploads: list[UploadFile],
    audio_uploads: list[UploadFile],
    transcriptions: list[str],
) -> tuple[list[Path], list[Path]]:
    """Save multipart files/audio and link them to the user message. Returns (file_paths, audio_paths)."""
    upload_root = _session_upload_root(session_id)
    file_paths: list[Path] = []
    audio_paths: list[Path] = []

    for upload in file_uploads:
        data = await upload.read()
        if not data:
            raise APIError("validation_error", "Пустой файл", detail="files")
        safe = _safe_filename(upload.filename)
        dest = upload_root / f"{uuid.uuid4().hex[:10]}_{safe}"
        dest.write_bytes(data)
        file_paths.append(dest)
        await _attach_file_to_message(session_id, message_id, dest, safe, len(data))

    for index, upload in enumerate(audio_uploads):
        data = await upload.read()
        if not data:
            raise APIError("validation_error", "Пустой файл audio", detail="audio")
        safe = _safe_filename(upload.filename)
        if not safe.lower().endswith((".m4a", ".mp4", ".ogg", ".wav", ".webm", ".mp3")):
            base = safe.rsplit(".", 1)[0] if "." in safe else safe
            safe = f"{base}.m4a"
        dest = voice_upload_path(session_id, safe)
        dest.write_bytes(data)
        audio_paths.append(dest)
        transcription = transcriptions[index] if index < len(transcriptions) else ""
        await attach_voice_to_message(session_id, message_id, dest, safe, len(data), transcription)

    return file_paths, audio_paths


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


async def _run_compose_pipeline(
    *,
    sid: int,
    tid: int,
    query_text: str,
    use_kb: bool,
    attached_files: list[Path],
    wants_sse: bool,
) -> Response:
    if wants_sse:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        err_holder: list[BaseException | None] = [None]

        async def on_chunk(chunk: str) -> None:
            await queue.put(chunk)

        async def run_pipeline() -> None:
            try:
                qps = QueryProcessingService()
                await qps.process_query_for_api(
                    query_text,
                    sid,
                    tid,
                    use_knowledge_base=use_kb,
                    attached_files=attached_files or None,
                    save_user_message=False,
                    on_chunk=on_chunk,
                )
            except BaseException as e:
                err_holder[0] = e
            finally:
                await queue.put(None)

        return StreamingResponse(
            _stream_assistant_sse(
                session_id=sid,
                queue=queue,
                err_holder=err_holder,
                run_pipeline=run_pipeline,
            ),
            media_type="text/event-stream",
            headers=SSE_STREAM_HEADERS,
        )

    try:
        qps = QueryProcessingService()
        await qps.process_query_for_api(
            query_text,
            sid,
            tid,
            use_knowledge_base=use_kb,
            attached_files=attached_files or None,
            save_user_message=False,
        )
    except RuntimeError as e:
        raise APIError("processing_error", str(e), status_code=500) from e

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    payload = {"messages": await enrich_session_messages(sid, all_msgs)}
    return JSONResponse(content=payload, status_code=201)


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

        return StreamingResponse(
            _stream_assistant_sse(
                session_id=sid,
                queue=queue,
                err_holder=err_holder,
                run_pipeline=run_pipeline,
            ),
            media_type="text/event-stream",
            headers=SSE_STREAM_HEADERS,
        )

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

        return StreamingResponse(
            _stream_assistant_sse(
                session_id=sid,
                queue=queue,
                err_holder=err_holder,
                run_pipeline=run_pipeline,
            ),
            media_type="text/event-stream",
            headers=SSE_STREAM_HEADERS,
        )

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


@router.post("/{session_id}/messages/compose")
async def post_compose_message(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    content: str = Form(default=""),
    use_knowledge_base: str = Form(default="true"),
    audio_transcriptions: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    audio: list[UploadFile] = File(default=[]),
    accept: Annotated[str | None, Header()] = None,
) -> Response:
    """
    Одно user-сообщение: опциональный текст, несколько files[] и audio[] + audio_transcriptions (JSON-массив).
    SSE — как у POST …/messages при Accept: text/event-stream.
    """
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])
    tid = int(user["telegram_id"])
    use_kb = _parse_use_kb(use_knowledge_base)
    wants_sse = accept and "text/event-stream" in accept.lower()

    file_uploads = [item for item in files if item.filename]
    audio_uploads = [item for item in audio if item.filename]
    if not (content or "").strip() and not file_uploads and not audio_uploads:
        raise APIError(
            "validation_error",
            "Нужен content, files или audio",
            detail="content",
        )

    transcriptions = _parse_audio_transcriptions(audio_transcriptions, len(audio_uploads))
    query_text = _compose_query_text(content, len(file_uploads), transcriptions)

    from utils.db_helpers import get_db

    db = await get_db()
    user_msg = await db.add_message(sid, "user", query_text)
    message_id = int(user_msg["id"])

    saved_paths: list[Path] = []
    try:
        file_paths, audio_paths = await _persist_compose_uploads(
            sid,
            message_id,
            file_uploads,
            audio_uploads,
            transcriptions,
        )
        saved_paths = file_paths + audio_paths
    except APIError:
        _cleanup_paths(saved_paths)
        raise
    except Exception:
        _cleanup_paths(saved_paths)
        raise

    try:
        return await _run_compose_pipeline(
            sid=sid,
            tid=tid,
            query_text=query_text,
            use_kb=use_kb,
            attached_files=file_paths,
            wants_sse=bool(wants_sse),
        )
    except APIError:
        raise
    except Exception:
        _cleanup_paths(saved_paths)
        raise
