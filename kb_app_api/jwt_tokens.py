"""Access JWT + opaque refresh tokens for KB App API."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from config import config


def _secret() -> str:
    secret = (getattr(config, "KB_APP_JWT_SECRET", None) or "").strip()
    if not secret:
        # Dev/test fallback — production must set KB_APP_JWT_SECRET
        secret = (config.KB_APP_API_TOKEN or "dev-insecure-jwt-secret").strip()
    return secret


def access_ttl_seconds() -> int:
    return int(getattr(config, "KB_APP_ACCESS_TTL_SEC", 3600) or 3600)


def refresh_ttl_seconds() -> int:
    return int(getattr(config, "KB_APP_REFRESH_TTL_SEC", 60 * 60 * 24 * 30) or 2_592_000)


def create_access_token(*, user_id: int, login: str, role: str) -> tuple[str, int]:
    ttl = access_ttl_seconds()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "login": login,
        "role": role,
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(payload, _secret(), algorithm="HS256")
    return token, ttl


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def new_refresh_token() -> tuple[str, str, datetime]:
    """Returns (raw_token, sha256_hex, expires_at UTC)."""
    raw = secrets.token_urlsafe(48)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl_seconds())
    return raw, digest, expires


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
