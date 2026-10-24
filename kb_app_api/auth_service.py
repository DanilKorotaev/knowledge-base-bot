"""Register / login / refresh / password + optional Nextcloud provision."""
from __future__ import annotations

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
from kb_app_api.nextcloud_provision import (
    NextcloudProvisionError,
    create_nextcloud_user,
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
        try:
            create_nextcloud_user(
                userid=login,
                password=password,
                email=email,
                display_name=login,
                quota=config.KB_APP_DEFAULT_QUOTA,
            )
        except NextcloudProvisionError as exc:
            logger.warning("NC provision failed for %s: %s", login, exc)
            # Account still usable in KB; admin can retry NC later
    return user


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
        must_change_password=False,
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
    await db.revoke_all_refresh_sessions(int(user["id"]))


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
