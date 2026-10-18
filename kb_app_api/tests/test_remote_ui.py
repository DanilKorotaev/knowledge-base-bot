"""Tests for allowlisted absolute-URL remote-ui proxy."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from config import config
from kb_app_api.main import app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(config, "KB_APP_API_TOKEN", "test-token")
    monkeypatch.setattr(config, "REMOTE_UI_HOST_ALLOWLIST", ["127.0.0.1", "localhost"])
    monkeypatch.setattr(config, "REMOTE_UI_ALLOWED_SCHEMES", ["http", "https"])
    return TestClient(app)


def test_allowlist(client: TestClient) -> None:
    resp = client.get(
        "/api/remote-ui/allowlist",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 200
    assert "127.0.0.1" in resp.json()["hosts"]


def test_host_forbidden(client: TestClient) -> None:
    resp = client.get(
        "/api/remote-ui",
        params={"url": "http://evil.example/v1/ui/home"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 403


def test_proxy_get(client: TestClient) -> None:
    fake = MagicMock()
    fake.status_code = 200
    fake.content = b'{"schema_version":1,"screen":{"type":"vstack","id":"root","children":[]}}'
    fake.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.request = AsyncMock(return_value=fake)

    with patch("kb_app_api.routes.remote_ui.httpx.AsyncClient", return_value=mock_client):
        resp = client.get(
            "/api/remote-ui",
            params={"url": "http://127.0.0.1:8095/v1/ui/home?x=1"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200
    assert resp.json()["schema_version"] == 1
    call_args = mock_client.request.await_args
    assert call_args.args[0] == "GET"
    assert call_args.args[1] == "http://127.0.0.1:8095/v1/ui/home?x=1"


def test_proxy_upstream_timeout(client: TestClient) -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("t"))

    with patch("kb_app_api.routes.remote_ui.httpx.AsyncClient", return_value=mock_client):
        resp = client.get(
            "/api/remote-ui",
            params={"url": "http://127.0.0.1:8095/v1/ui/home"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 504
