"""Create / update Nextcloud users via OCS Provisioning API."""
from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth

from config import config

logger = logging.getLogger(__name__)


class NextcloudProvisionError(RuntimeError):
    pass


def _enabled() -> bool:
    return bool(getattr(config, "KB_APP_NC_PROVISION_ENABLED", True)) and bool(
        config.NEXTCLOUD_URL and config.NEXTCLOUD_BOT_USERNAME and config.NEXTCLOUD_BOT_PASSWORD
    )


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(config.NEXTCLOUD_BOT_USERNAME, config.NEXTCLOUD_BOT_PASSWORD)


def _ocs_base() -> str:
    return config.NEXTCLOUD_URL.rstrip("/") + "/ocs/v1.php/cloud"


def create_nextcloud_user(
    *,
    userid: str,
    password: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    quota: Optional[str] = None,
) -> None:
    """
    Create NC user. Requires bot credentials with admin (or user-manager) rights.
    quota e.g. \"5 GB\" or \"none\".
    """
    if not _enabled():
        logger.info("NC provision skipped (disabled or NC not configured) for %s", userid)
        return

    url = f"{_ocs_base()}/users"
    data: dict[str, Any] = {"userid": userid, "password": password}
    if email:
        data["email"] = email
    if display_name:
        data["displayName"] = display_name
    if quota:
        data["quota"] = quota

    try:
        resp = requests.post(
            url,
            auth=_auth(),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data=data,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise NextcloudProvisionError(f"NC create user network error: {exc}") from exc

    # 102 = user already exists in some NC versions via OCS meta statuscode
    if resp.status_code in (200, 201):
        logger.info("NC user created: %s", userid)
        return
    # Conflict / already exists
    if resp.status_code == 400 and "already" in (resp.text or "").lower():
        logger.info("NC user already exists: %s", userid)
        return
    try:
        body = resp.json()
        status = int(body.get("ocs", {}).get("meta", {}).get("statuscode", 0))
        if status in (100, 102):  # 100 ok, 102 exists
            return
        message = body.get("ocs", {}).get("meta", {}).get("message")
    except Exception:
        message = resp.text[:300]
    raise NextcloudProvisionError(
        f"NC create user failed HTTP {resp.status_code}: {message}"
    )


def set_nextcloud_password(userid: str, password: str) -> None:
    if not _enabled():
        logger.info("NC password update skipped for %s", userid)
        return
    url = f"{_ocs_base()}/users/{userid}"
    try:
        resp = requests.put(
            url,
            auth=_auth(),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data={"key": "password", "value": password},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise NextcloudProvisionError(f"NC set password network error: {exc}") from exc
    if resp.status_code not in (200, 201):
        raise NextcloudProvisionError(
            f"NC set password failed HTTP {resp.status_code}: {resp.text[:300]}"
        )


def set_nextcloud_quota(userid: str, quota: str) -> None:
    if not _enabled():
        return
    url = f"{_ocs_base()}/users/{userid}"
    try:
        resp = requests.put(
            url,
            auth=_auth(),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data={"key": "quota", "value": quota},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise NextcloudProvisionError(f"NC set quota network error: {exc}") from exc
    if resp.status_code not in (200, 201):
        raise NextcloudProvisionError(
            f"NC set quota failed HTTP {resp.status_code}: {resp.text[:300]}"
        )
