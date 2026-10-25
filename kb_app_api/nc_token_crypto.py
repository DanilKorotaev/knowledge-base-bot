"""Encrypt / decrypt Nextcloud App Passwords at rest (Fernet).

Key: ``KB_NC_TOKEN_KEY`` — url-safe base64 Fernet key, or any passphrase
(hashed to a Fernet key). If unset, derives from ``KB_APP_JWT_SECRET``
(fine for single-node staging; set an explicit key in production).
"""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from config import config

logger = logging.getLogger(__name__)


def _fernet_key_bytes() -> bytes:
    raw = (getattr(config, "KB_NC_TOKEN_KEY", None) or "").strip()
    if not raw:
        secret = (config.KB_APP_JWT_SECRET or "dev-insecure-nc-token").encode("utf-8")
        digest = hashlib.sha256(b"kb-nc-token-v1:" + secret).digest()
        return base64.urlsafe_b64encode(digest)
    # Accept a ready Fernet key, or treat as passphrase.
    try:
        candidate = raw.encode("utf-8")
        Fernet(candidate)  # validate
        return candidate
    except Exception:
        digest = hashlib.sha256(raw.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_fernet_key_bytes())


def encrypt_nc_token(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("empty app password")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_nc_token(ciphertext: str) -> str:
    if not ciphertext:
        raise ValueError("empty ciphertext")
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("cannot decrypt nc app password (wrong KB_NC_TOKEN_KEY?)") from exc


def try_decrypt_nc_token(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return decrypt_nc_token(ciphertext)
    except ValueError:
        logger.warning("Failed to decrypt stored nc_app_password_enc")
        return None
