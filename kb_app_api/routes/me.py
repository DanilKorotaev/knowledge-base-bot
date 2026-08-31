from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from kb_app_api.deps import get_api_user
from kb_app_api.errors import APIError
from kb_app_api.health_paths import validate_health_data_relative
from utils.db_helpers import get_db

router = APIRouter(prefix="/me", tags=["me"])


class UserSettingsResponse(BaseModel):
    health_data_relative: str = Field(..., description="Relative folder under the vault for Health JSON exports")


class PatchUserSettingsBody(BaseModel):
    health_data_relative: str | None = Field(
        default=None,
        description="Relative folder under the vault (no leading slash, no ..)",
    )


@router.get("/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> UserSettingsResponse:
    db = await get_db()
    relative = await db.get_user_health_data_relative(user["id"])
    return UserSettingsResponse(health_data_relative=relative)


@router.patch("/settings", response_model=UserSettingsResponse)
async def patch_user_settings(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    body: PatchUserSettingsBody,
) -> UserSettingsResponse:
    if body.health_data_relative is None:
        raise APIError("validation_error", "Нужно передать health_data_relative", detail="health_data_relative")
    try:
        validated = validate_health_data_relative(body.health_data_relative)
    except ValueError as exc:
        raise APIError(
            "validation_error",
            "Некорректный health_data_relative",
            detail=str(exc),
        )
    db = await get_db()
    relative = await db.set_user_health_data_relative(user["id"], validated)
    return UserSettingsResponse(health_data_relative=relative)
