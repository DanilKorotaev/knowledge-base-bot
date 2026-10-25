"""Create / update Nextcloud users via OCS Provisioning API + App Password mint."""
from __future__ import annotations

import logging
import time
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


def _nc_configured() -> bool:
    return bool(config.NEXTCLOUD_URL)


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(config.NEXTCLOUD_BOT_USERNAME, config.NEXTCLOUD_BOT_PASSWORD)


def _ocs_base() -> str:
    return config.NEXTCLOUD_URL.rstrip("/") + "/ocs/v1.php/cloud"


def _timeout() -> float:
    try:
        return max(1.0, float(getattr(config, "KB_APP_NC_PROVISION_TIMEOUT_SEC", 5) or 5))
    except (TypeError, ValueError):
        return 5.0


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
            timeout=_timeout(),
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
            timeout=_timeout(),
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
            timeout=_timeout(),
        )
    except requests.RequestException as exc:
        raise NextcloudProvisionError(f"NC set quota network error: {exc}") from exc
    if resp.status_code not in (200, 201):
        raise NextcloudProvisionError(
            f"NC set quota failed HTTP {resp.status_code}: {resp.text[:300]}"
        )


def mint_nextcloud_app_password(
    *,
    userid: str,
    password: str,
    retries: int = 4,
    retry_delay_sec: float = 0.6,
) -> str:
    """
    Mint a per-user App Password via OCS core/getapppassword.

    Must authenticate with the user's *login password* (not an existing app password).
    Retries briefly after user create (NC may need a moment).
    """
    if not _nc_configured() or not getattr(config, "KB_APP_NC_PROVISION_ENABLED", True):
        raise NextcloudProvisionError("NC app-password mint skipped (disabled or NC not configured)")

    url = config.NEXTCLOUD_URL.rstrip("/") + "/ocs/v2.php/core/getapppassword"
    last_err: Optional[str] = None
    for attempt in range(max(1, retries)):
        try:
            resp = requests.get(
                url,
                auth=HTTPBasicAuth(userid, password),
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
                timeout=_timeout(),
            )
        except requests.RequestException as exc:
            last_err = f"network: {exc}"
            time.sleep(retry_delay_sec * (attempt + 1))
            continue

        if resp.status_code in (200, 201):
            try:
                data = resp.json()
                app_pw = (
                    data.get("ocs", {})
                    .get("data", {})
                    .get("apppassword")
                )
            except Exception:
                app_pw = None
            if app_pw:
                logger.info("NC app password minted for %s", userid)
                return str(app_pw)
            last_err = f"empty apppassword in response: {resp.text[:200]}"
        else:
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            # 401 right after create — wait and retry
            if resp.status_code in (401, 403, 404, 503):
                time.sleep(retry_delay_sec * (attempt + 1))
                continue
            break

        time.sleep(retry_delay_sec * (attempt + 1))

    raise NextcloudProvisionError(
        f"NC mint app password failed for {userid}: {last_err}"
    )
