"""Register / login / refresh / password + optional Nextcloud provision."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from config import config
from kb_app_api.errors import APIError
from kb_app_api.jwt_tokens import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
)
from kb_app_api.kb_folder import normalize_kb_folder
from kb_app_api.nc_token_crypto import encrypt_nc_token
from kb_app_api.nextcloud_provision import (
    NextcloudProvisionError,
    create_nextcloud_user,
    mint_nextcloud_app_password,
    set_nextcloud_password,
)
from kb_app_api.passwords import hash_password, verify_password
from kb_app_api.vault_paths import ensure_vault_dir, vault_relative_for_login

logger = logging.getLogger(__name__)

_LOGIN_RE = re.compile(r"^[a-zA-Z0-9._-]{3,64}$")


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "login": user.get("login"),
        "email": user.get("email"),
        "role": user.get("role") or "user",
        "must_change_password": bool(user.get("must_change_password")),
        "cursor_isolation": user.get("cursor_isolation") or "strict",
        "vault_root_relative": user.get("vault_root_relative"),
        "nextcloud_username": user.get("nextcloud_username"),
        "kb_folder": user.get("kb_folder") or "/",
        "has_nc_app_password": bool(user.get("nc_app_password_enc")),
    }


async def issue_tokens(db: Any, user: dict[str, Any]) -> dict[str, Any]:
    access, expires_in = create_access_token(
        user_id=int(user["id"]),
        login=str(user.get("login") or ""),
        role=str(user.get("role") or "user"),
    )
    raw_refresh, refresh_hash, refresh_exp = new_refresh_token()
    await db.create_refresh_session(int(user["id"]), refresh_hash, refresh_exp)
    ensure_vault_dir(user)
    return {
        "access_token": access,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": _public_user(user),
    }


def _validate_login(login: str) -> str:
    login = login.strip()
    if not _LOGIN_RE.match(login):
        raise APIError(
            "validation_error",
            "login: 3–64 символа [a-zA-Z0-9._-]",
            detail="login",
            status_code=422,
        )
    return login


def _validate_password(password: str) -> str:
    if len(password) < 8:
        raise APIError(
            "validation_error",
            "Пароль минимум 8 символов",
            detail="password",
            status_code=422,
        )
    return password


async def register_user(
    db: Any,
    *,
    login: str,
    password: str,
    email: Optional[str] = None,
    role: str = "user",
    is_admin: bool = False,
    signup_source: str = "self",
    must_change_password: bool = False,
    provision_nc: bool = True,
) -> dict[str, Any]:
    login = _validate_login(login)
    password = _validate_password(password)
    existing = await db.get_user_by_login(login)
    if existing:
        raise APIError("conflict", "Пользователь уже существует", status_code=409)

    isolation = (config.KB_APP_DEFAULT_CURSOR_ISOLATION or "strict").lower()
    if isolation not in ("strict", "host"):
        isolation = "strict"
    vault_rel = vault_relative_for_login(login)
    user = await db.create_app_user(
        login=login,
        password_hash=hash_password(password),
        email=email,
        role=role,
        vault_root_relative=vault_rel,
        cursor_isolation=isolation,
        must_change_password=must_change_password,
        signup_source=signup_source,
        nextcloud_username=login,
        is_admin=is_admin or role == "admin",
    )
    ensure_vault_dir(user)
    if provision_nc and config.KB_APP_NC_PROVISION_ENABLED:
        # Never block the API worker on Nextcloud OCS — run in background.
        asyncio.create_task(
            _provision_nc_user_background(
                user_id=int(user["id"]),
                login=login,
                password=password,
                email=email,
                quota=config.KB_APP_DEFAULT_QUOTA,
            )
        )
    return user


async def _store_minted_app_password(db: Any, user_id: int, app_password: str) -> None:
    enc = encrypt_nc_token(app_password)
    await db.set_user_nc_app_password_enc(user_id, enc)


async def _provision_nc_user_background(
    *,
    user_id: int,
    login: str,
    password: str,
    email: Optional[str],
    quota: Optional[str],
) -> None:
    try:
        await asyncio.to_thread(
            create_nextcloud_user,
            userid=login,
            password=password,
            email=email,
            display_name=login,
            quota=quota,
        )
        app_pw = await asyncio.to_thread(
            mint_nextcloud_app_password,
            userid=login,
            password=password,
        )
        from utils.db_helpers import get_db

        db = await get_db()
        await _store_minted_app_password(db, user_id, app_pw)
    except NextcloudProvisionError as exc:
        logger.warning("NC provision/mint failed for %s: %s", login, exc)
    except Exception:
        logger.exception("NC provision unexpected error for %s", login)


async def login_user(db: Any, *, login: str, password: str) -> dict[str, Any]:
    login = login.strip()
    user = await db.get_user_by_login(login)
    if not user or not user.get("password_hash"):
        raise APIError("unauthorized", "Неверный логин или пароль", status_code=401)
    if not verify_password(password, user["password_hash"]):
        raise APIError("unauthorized", "Неверный логин или пароль", status_code=401)
    if config.ACCESS_MODE == "restricted" and not user.get("is_allowed"):
        if not config.KB_APP_API_BYPASS_ACCESS_CHECK:
            raise APIError("forbidden", "Пользователь не разрешён", status_code=403)
    return await issue_tokens(db, user)


async def refresh_tokens(db: Any, *, refresh_token: str) -> dict[str, Any]:
    digest = hash_refresh_token(refresh_token)
    session = await db.get_refresh_session(digest)
    if not session or session.get("revoked_at"):
        raise APIError("unauthorized", "Недействительный refresh", status_code=401)
    expires = session["expires_at"]
    if isinstance(expires, str):
        expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise APIError("unauthorized", "Refresh истёк", status_code=401)
    user = await db.get_user_by_id(int(session["user_id"]))
    if not user:
        raise APIError("unauthorized", "Пользователь не найден", status_code=401)
    await db.revoke_refresh_session(digest)
    return await issue_tokens(db, user)


async def logout_user(db: Any, *, refresh_token: Optional[str], user_id: Optional[int]) -> None:
    if refresh_token:
        await db.revoke_refresh_session(hash_refresh_token(refresh_token))
    elif user_id is not None:
        await db.revoke_all_refresh_sessions(int(user_id))


async def change_password(
    db: Any,
    *,
    user: dict[str, Any],
    current_password: Optional[str],
    new_password: str,
    skip_current_check: bool = False,
    must_change_password: bool = False,
) -> None:
    new_password = _validate_password(new_password)
    if not skip_current_check:
        if not current_password or not verify_password(
            current_password, user.get("password_hash") or ""
        ):
            raise APIError("unauthorized", "Неверный текущий пароль", status_code=401)
    await db.update_user_password(
        int(user["id"]),
        hash_password(new_password),
        must_change_password=must_change_password,
    )
    nc_user = user.get("nextcloud_username") or user.get("login")
    if nc_user and config.KB_APP_NC_PROVISION_ENABLED:
        try:
            set_nextcloud_password(str(nc_user), new_password)
        except NextcloudProvisionError as exc:
            logger.error("NC password sync failed for %s: %s", nc_user, exc)
            raise APIError(
                "bad_gateway",
                "Пароль обновлён в KB, но Nextcloud не принял смену",
                detail=str(exc),
                status_code=502,
            ) from exc
        try:
            app_pw = mint_nextcloud_app_password(
                userid=str(nc_user), password=new_password
            )
            await _store_minted_app_password(db, int(user["id"]), app_pw)
        except NextcloudProvisionError as exc:
            # Login password already synced; clear stale token so we do not keep a bad secret.
            logger.warning("NC remint app password failed for %s: %s", nc_user, exc)
            await db.set_user_nc_app_password_enc(int(user["id"]), None)
    await db.revoke_all_refresh_sessions(int(user["id"]))


async def update_kb_folder(db: Any, *, user: dict[str, Any], kb_folder: str) -> dict[str, Any]:
    folder = normalize_kb_folder(kb_folder)
    await db.set_user_kb_folder(int(user["id"]), folder)
    updated = await db.get_user_by_id(int(user["id"]))
    return updated or {**user, "kb_folder": folder}


def _parent_path(path: str) -> str | None:
    folder = normalize_kb_folder(path)
    if folder == "/":
        return None
    parent = "/".join(folder.rstrip("/").split("/")[:-1])
    return parent if parent else "/"


def _nc_folder_picker_payload(
    user: dict[str, Any],
    folders: list[dict[str, str]],
    *,
    browse_path: str = "/",
) -> dict[str, Any]:
    current = normalize_kb_folder(user.get("kb_folder"))
    browse = normalize_kb_folder(browse_path)
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in folders:
        rel = (item.get("path") or "").strip().strip("/")
        if not rel:
            continue
        path = normalize_kb_folder(rel)
        if path in seen:
            continue
        seen.add(path)
        name = (item.get("name") or "").strip() or path.rsplit("/", 1)[-1]
        items.append({"path": path, "name": name})
    return {
        "current": current,
        "browse_path": browse,
        "parent_path": _parent_path(browse),
        "has_nc_app_password": bool(user.get("nc_app_password_enc")),
        "folders": items,
    }


async def list_nc_folders(
    user: dict[str, Any], *, path: str = "/"
) -> dict[str, Any]:
    """List child folders under ``path`` in the user's NC home (Settings picker)."""
    from services.nextcloud_service import NextCloudService

    browse = normalize_kb_folder(path)
    nc = NextCloudService.for_user(user, at_home=True)
    if nc is None or not nc.enabled:
        raise APIError(
            "nextcloud_unavailable",
            "Nextcloud App Password недоступен — войдите снова или смените пароль в приложении",
            status_code=503,
        )
    remote = "" if browse == "/" else browse.lstrip("/")
    children = await nc.list_child_directories(remote)
    return _nc_folder_picker_payload(user, children, browse_path=browse)


async def create_nc_folder(
    db: Any,
    *,
    user: dict[str, Any],
    name: str,
    parent: str = "/",
    select: bool = True,
) -> dict[str, Any]:
    """Create a folder under ``parent`` in NC home; optionally select it as kb_folder."""
    from services.nextcloud_service import NextCloudService

    raw = (name or "").strip().strip("/")
    if not raw or "/" in raw or raw in (".", ".."):
        raise APIError(
            "validation_error",
            "Имя папки: один сегмент без /",
            detail="name",
            status_code=422,
        )
    parent_path = normalize_kb_folder(parent)
    folder = normalize_kb_folder(
        f"{parent_path.rstrip('/')}/{raw}" if parent_path != "/" else f"/{raw}"
    )
    nc = NextCloudService.for_user(user, at_home=True)
    if nc is None or not nc.enabled:
        raise APIError(
            "nextcloud_unavailable",
            "Nextcloud App Password недоступен",
            status_code=503,
        )
    try:
        await asyncio.to_thread(nc.create_directory, folder.lstrip("/"))
    except Exception as exc:
        logger.warning("NC create folder failed for %s: %s", user.get("login"), exc)
        raise APIError(
            "bad_gateway",
            "Не удалось создать папку в Nextcloud",
            detail=str(exc),
            status_code=502,
        ) from exc

    if select:
        user = await update_kb_folder(db, user=user, kb_folder=folder)
    # Stay inside the new folder so nested create/browse continues naturally.
    children = await nc.list_child_directories(folder.lstrip("/"))
    return _nc_folder_picker_payload(user, children, browse_path=folder)


async def maybe_bootstrap_admin(db: Any) -> None:
    login = (config.KB_BOOTSTRAP_ADMIN_LOGIN or "").strip()
    password = config.KB_BOOTSTRAP_ADMIN_PASSWORD or ""
    if not login or not password:
        return
    if await db.count_login_users() > 0:
        return
    logger.warning("Bootstrapping admin user %s", login)
    await register_user(
        db,
        login=login,
        password=password,
        email=config.KB_BOOTSTRAP_ADMIN_EMAIL,
        role="admin",
        is_admin=True,
        signup_source="bootstrap",
        provision_nc=True,
    )
