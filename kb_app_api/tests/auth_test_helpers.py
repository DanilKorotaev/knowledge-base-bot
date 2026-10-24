"""Helpers: register/login and Authorization header for API tests."""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


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
