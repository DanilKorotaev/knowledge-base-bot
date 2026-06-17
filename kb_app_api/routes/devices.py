from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user

router = APIRouter(prefix="/devices", tags=["devices"])


class RegisterDeviceBody(BaseModel):
    device_token: str = Field(..., min_length=1, max_length=512)
    platform: Literal["ios"] = "ios"
    apns_environment: Literal["sandbox", "production"] = "production"
    app_version: str | None = Field(default=None, max_length=50)


@router.post("", status_code=204, response_class=Response)
async def register_device(
    body: RegisterDeviceBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> Response:
    from utils.db_helpers import get_db

    db = await get_db()
    await db.upsert_user_device(
        user_id=int(user["id"]),
        device_token=body.device_token.strip(),
        platform=body.platform,
        apns_environment=body.apns_environment,
        app_version=body.app_version,
    )
    return Response(status_code=204)


@router.delete("/{device_token}", status_code=204, response_class=Response)
async def unregister_device(
    device_token: str,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> Response:
    from utils.db_helpers import get_db

    db = await get_db()
    await db.delete_user_device(int(user["id"]), device_token.strip())
    return Response(status_code=204)
