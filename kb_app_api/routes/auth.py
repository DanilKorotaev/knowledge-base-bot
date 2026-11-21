"""KB App auth: register / login / refresh / logout / change-password / me."""
from __future__ import annotations

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from config import config
from kb_app_api import auth_service
from kb_app_api.deps import get_api_user, get_api_user_optional
from kb_app_api.errors import APIError

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    login: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=200)
    email: Optional[str] = Field(default=None, max_length=255)


class LoginBody(BaseModel):
    login: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=200)


class RefreshBody(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None


class ChangePasswordBody(BaseModel):
    current_password: Optional[str] = None
    new_password: str = Field(..., min_length=8, max_length=200)


class PatchMeBody(BaseModel):
    kb_folder: Optional[str] = Field(default=None, max_length=512)


class TelegramWebAppBody(BaseModel):
    init_data: str = Field(..., min_length=10)


class CreateNcFolderBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    parent: Optional[str] = Field(default="/", max_length=512)
    select: bool = True


@router.post("/register")
async def register(body: RegisterBody) -> dict[str, Any]:
    if not config.KB_APP_OPEN_SIGNUP:
        raise APIError(
            "forbidden",
            "Публичная регистрация отключена (invite_only)",
            status_code=403,
        )
    from utils.db_helpers import get_db

    db = await get_db()
    user = await auth_service.register_user(
        db,
        login=body.login,
        password=body.password,
        email=body.email,
        signup_source="self",
    )
    return await auth_service.issue_tokens(db, user)


@router.post("/telegram/webapp")
async def telegram_webapp(body: TelegramWebAppBody) -> dict[str, Any]:
    """Exchange Telegram Mini App initData for the same JWT pair as login."""
    from miniapp.api.auth import validate_init_data
    from kb_app_api.telegram_link import LINK_REQUIRED, telegram_linked
    from utils.db_helpers import get_db

    user_data = validate_init_data(body.init_data, config.TELEGRAM_TOKEN or "")
    telegram_id = int(user_data["id"]) if user_data and user_data.get("id") else 0
    if telegram_id <= 0:
        raise APIError("unauthorized", "Не удалось проверить Telegram", status_code=401)

    db = await get_db()
    user = await db.get_user_by_telegram_id(telegram_id)
    if not user or not user.get("login") or not telegram_linked(user):
        raise APIError("forbidden", LINK_REQUIRED, status_code=403)
    if user.get("is_allowed") is False:
        raise APIError("forbidden", "Аккаунт отключён", status_code=403)
    return await auth_service.issue_tokens(db, user)


@router.post("/login")
async def login(body: LoginBody) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    return await auth_service.login_user(db, login=body.login, password=body.password)


@router.post("/refresh")
async def refresh(body: RefreshBody) -> dict[str, Any]:
    from utils.db_helpers import get_db

    db = await get_db()
    return await auth_service.refresh_tokens(db, refresh_token=body.refresh_token)


@router.post("/logout")
async def logout(
    body: LogoutBody | None = None,
    user: Annotated[dict[str, Any] | None, Depends(get_api_user_optional)] = None,
) -> dict[str, str]:
    from utils.db_helpers import get_db

    db = await get_db()
    refresh_token = body.refresh_token if body else None
    await auth_service.logout_user(
        db,
        refresh_token=refresh_token,
        user_id=int(user["id"]) if user else None,
    )
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, str]:
    from utils.db_helpers import get_db

    db = await get_db()
    # Reload full user (needs password_hash)
    full = await db.get_user_by_id(int(user["id"]))
    if not full:
        raise APIError("unauthorized", "Пользователь не найден", status_code=401)
    skip = bool(full.get("must_change_password"))
    await auth_service.change_password(
        db,
        user=full,
        current_password=body.current_password,
        new_password=body.new_password,
        skip_current_check=skip,
    )
    return {"status": "ok"}


@router.get("/me")
async def me(user: Annotated[dict[str, Any], Depends(get_api_user)]) -> dict[str, Any]:
    return {"user": auth_service._public_user(user)}


@router.patch("/me")
async def patch_me(
    body: PatchMeBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    if body.kb_folder is None:
        return {"user": auth_service._public_user(user)}
    db = await get_db()
    updated = await auth_service.update_kb_folder(db, user=user, kb_folder=body.kb_folder)
    return {"user": auth_service._public_user(updated)}


@router.get("/nc-folders")
async def list_nc_folders(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
    path: str = "/",
) -> dict[str, Any]:
    """List child folders under ``path`` in the user's Nextcloud home (kb_folder picker)."""
    from utils.db_helpers import get_db

    db = await get_db()
    full = await db.get_user_by_id(int(user["id"]))
    if not full:
        raise APIError("unauthorized", "Пользователь не найден", status_code=401)
    return await auth_service.list_nc_folders(full, path=path)


@router.post("/nc-folders")
async def create_nc_folder(
    body: CreateNcFolderBody,
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """Create a folder under ``parent``; by default also sets it as kb_folder."""
    from utils.db_helpers import get_db

    db = await get_db()
    full = await db.get_user_by_id(int(user["id"]))
    if not full:
        raise APIError("unauthorized", "Пользователь не найден", status_code=401)
    return await auth_service.create_nc_folder(
        db,
        user=full,
        name=body.name,
        parent=body.parent or "/",
        select=body.select,
    )


@router.get("/signup-status")
async def signup_status() -> dict[str, Any]:
    return {"open_signup": bool(config.KB_APP_OPEN_SIGNUP)}


@router.post("/telegram/link")
async def start_telegram_link(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    """One-time code. The user sends ``/link CODE`` to the bot."""
    from utils.db_helpers import get_db

    from kb_app_api.telegram_link import issue_link_code

    db = await get_db()
    return await issue_link_code(db, int(user["id"]), purpose="link")


@router.delete("/telegram/link")
async def delete_telegram_link(
    user: Annotated[dict[str, Any], Depends(get_api_user)],
) -> dict[str, Any]:
    from utils.db_helpers import get_db

    from kb_app_api.telegram_link import unlink_telegram

    db = await get_db()
    updated = await unlink_telegram(db, int(user["id"]))
    return {"user": auth_service._public_user(updated)}
