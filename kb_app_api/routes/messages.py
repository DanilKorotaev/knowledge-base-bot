from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.serializers import message_to_kb
from kb_app_api.session_access import parse_session_id, require_session_for_user
from services.query_processing_service import QueryProcessingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["messages"])


class PostMessageBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=32000)
    use_knowledge_base: bool = True


@router.get("/{session_id}/messages")
async def get_messages(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    page: int = 1,
    per_page: int = 100,
) -> dict[str, Any]:
    if page < 1:
        raise APIError("validation_error", "page должен быть >= 1", detail="page")
    if per_page < 1 or per_page > 200:
        raise APIError("validation_error", "per_page должен быть 1…200", detail="per_page")

    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    from utils.db_helpers import get_db

    db = await get_db()
    all_msgs = await db.get_session_messages(sid)
    start = (page - 1) * per_page
    chunk = all_msgs[start : start + per_page]
    return {"messages": [message_to_kb(m) for m in chunk], "total": len(all_msgs)}


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
    payload = {"messages": [message_to_kb(m) for m in all_msgs]}
    return JSONResponse(content=payload, status_code=201)


@router.post("/{session_id}/attachments", status_code=501)
async def post_attachment(
    session_id: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    _ = session_id, user
    raise APIError(
        "not_implemented",
        "Загрузка вложений пока не реализована",
        status_code=501,
    )
