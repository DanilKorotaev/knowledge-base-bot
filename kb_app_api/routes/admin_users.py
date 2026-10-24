"""Admin REST: list/create/patch KB App users (role=admin)."""
from __future__ import annotations

import secrets
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config import config
from kb_app_api import auth_service
from kb_app_api.deps import require_admin
from kb_app_api.errors import APIError
router = APIRouter(prefix="/admin/users", tags=["admin"])


def _public(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u["id"],
        "login": u.get("login"),
        "email": u.get("email"),
        "role": u.get("role") or "user",
        "is_admin": bool(u.get("is_admin") or (u.get("role") == "admin")),
        "is_allowed": bool(u.get("is_allowed", True)),
        "must_change_password": bool(u.get("must_change_password")),
        "cursor_isolation": u.get("cursor_isolation") or "strict",
        "vault_root_relative": u.get("vault_root_relative"),
        "nextcloud_username": u.get("nextcloud_username"),
        "quota_bytes": u.get("quota_bytes"),
        "signup_source": u.get("signup_source"),
        "created_at": str(u.get("created_at") or ""),
    }


class CreateUserBody(BaseModel):
    login: str = Field(..., min_length=3, max_length=64)
    email: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=200,
        description="If omitted, a temporary password is generated",
    )
    role: str = Field(default="user", pattern="^(user|admin)$")
    cursor_isolation: Optional[str] = Field(default=None, pattern="^(strict|host)$")
    must_change_password: bool = True


class PatchUserBody(BaseModel):
    is_allowed: Optional[bool] = None
    cursor_isolation: Optional[str] = Field(default=None, pattern="^(strict|host)$")
    quota_bytes: Optional[int] = Field(default=None, ge=0)
    role: Optional[str] = Field(default=None, pattern="^(user|admin)$")
    email: Optional[str] = None


class ResetPasswordBody(BaseModel):
    password: Optional[str] = Field(default=None, min_length=8, max_length=200)
    must_change_password: bool = True


@router.get("")
async def list_users(
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    users = await db.list_app_users(limit=500, offset=0)
    return {"users": [_public(u) for u in users], "total": len(users)}


@router.post("", status_code=201)
async def create_user(
    body: CreateUserBody,
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    temp = body.password or secrets.token_urlsafe(12)
    isolation = body.cursor_isolation or config.KB_APP_DEFAULT_CURSOR_ISOLATION
    user = await auth_service.register_user(
        db,
        login=body.login,
        password=temp,
        email=body.email,
        role=body.role,
        is_admin=body.role == "admin",
        signup_source="admin",
        must_change_password=body.must_change_password,
        provision_nc=True,
    )
    if body.cursor_isolation:
        user = await db.update_app_user_fields(
            int(user["id"]), cursor_isolation=isolation
        ) or user
    out = _public(user)
    # Return temp password once (admin must share out-of-band until email works)
    out["temporary_password"] = temp
    return {"user": out}


@router.patch("/{user_id}")
async def patch_user(
    user_id: int,
    body: PatchUserBody,
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    is_admin = None
    if body.role is not None:
        is_admin = body.role == "admin"
    updated = await db.update_app_user_fields(
        user_id,
        is_allowed=body.is_allowed,
        cursor_isolation=body.cursor_isolation,
        quota_bytes=body.quota_bytes,
        role=body.role,
        is_admin=is_admin,
        email=body.email,
    )
    if not updated:
        raise APIError("not_found", "Пользователь не найден", status_code=404)
    if body.quota_bytes is not None and updated.get("nextcloud_username"):
        # Best-effort: NC quota as human string later; for now skip if bytes only
        pass
    return {"user": _public(updated)}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    body: ResetPasswordBody,
    _: Annotated[dict[str, Any], Depends(require_admin)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    user = await db.get_user_by_id(user_id)
    if not user or not user.get("login"):
        raise APIError("not_found", "Пользователь не найден", status_code=404)
    temp = body.password or secrets.token_urlsafe(12)
    await auth_service.change_password(
        db,
        user=user,
        current_password=None,
        new_password=temp,
        skip_current_check=True,
        must_change_password=body.must_change_password,
    )
    return {"status": "ok", "temporary_password": temp, "user_id": user_id}
