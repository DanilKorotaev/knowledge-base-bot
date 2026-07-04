from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.message_enrichment import enrich_session_messages
from kb_app_api.session_access import parse_session_id, require_session_for_user
from kb_app_api.structured_ui.mock_flow import apply_mock_ui_event
from kb_app_api.structured_ui.validate import StructuredUIValidationError, validate_document_size

router = APIRouter(prefix="/sessions", tags=["structured-ui"])

SUPPORTED_CLIENT_SCHEMA_VERSION = 1


class UIEventBody(BaseModel):
    action_id: str = Field(..., min_length=1, max_length=128)
    component_id: str = Field(..., min_length=1, max_length=128)
    client_schema_version: int = Field(default=1, ge=1, le=99)
    metadata: dict[str, Any] | None = None


@router.post("/{session_id}/ui-events")
async def post_ui_event(
    session_id: str,
    body: UIEventBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Apply a structured UI event and return the next screen (+ updated messages)."""
    sid = parse_session_id(session_id)
    await require_session_for_user(sid, user["id"])

    if body.client_schema_version > SUPPORTED_CLIENT_SCHEMA_VERSION:
        raise APIError(
            "unsupported_schema_version",
            "Client schema_version is newer than server supports",
            detail="client_schema_version",
            status_code=400,
        )

    if body.metadata:
        validate_document_size({"metadata": body.metadata})

    try:
        result = apply_mock_ui_event(action_id=body.action_id, component_id=body.component_id)
    except KeyError as exc:
        raise APIError(
            "validation_error",
            f"Unknown action_id: {body.action_id}",
            detail="action_id",
        ) from exc
    except StructuredUIValidationError as exc:
        raise APIError(exc.code, exc.message, detail=exc.detail, status_code=422) from exc

    from utils.db_helpers import get_db

    db = await get_db()
    if result.user_content:
        await db.add_message(sid, "user", result.user_content)

    assistant = await db.add_message(sid, "assistant", result.assistant_content)
    await db.set_message_structured_ui(int(assistant["id"]), result.screen)

    messages = await enrich_session_messages(sid, await db.get_session_messages(sid))
    return {
        "screen": result.screen,
        "messages": messages,
    }
