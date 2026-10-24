"""Helpers: register/login and Authorization header for API tests."""
from __future__ import annotations

import os
from typing import Any

from fastapi.testclient import TestClient


def apply_auth_test_env(*, jwt_secret: str = "test-jwt-secret") -> None:
    """Call from setUpModule *before* importing kb_app_api.main."""
    os.environ["KB_APP_JWT_SECRET"] = jwt_secret
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ.setdefault("ACCESS_MODE", "open")


def bearer_headers(
    client: TestClient,
    *,
    login: str = "smoketest",
    password: str = "test-pass-123",
    email: str | None = "smoke@example.com",
) -> dict[str, str]:
    reg = client.post(
        "/api/auth/register",
        json={"login": login, "password": password, "email": email},
    )
    if reg.status_code == 409:
        reg = client.post(
            "/api/auth/login",
            json={"login": login, "password": password},
        )
    assert reg.status_code == 200, reg.text
    data: dict[str, Any] = reg.json()
    token = data["access_token"]
    return {"Authorization": f"Bearer {token}"}
