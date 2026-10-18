"""Tests for generic remote-ui upstream proxy."""

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
    monkeypatch.setattr(
        config,
        "REMOTE_UI_UPSTREAMS",
        {"lyrics": "http://127.0.0.1:8095"},
    )
    return TestClient(app)


def test_list_upstreams(client: TestClient) -> None:
    resp = client.get("/api/remote-ui", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    assert resp.json()["upstreams"] == ["lyrics"]


def test_unknown_upstream(client: TestClient) -> None:
    resp = client.get(
        "/api/remote-ui/nope/v1/ui/home",
        headers={"Authorization": "Bearer test-token"},
    )
    assert resp.status_code == 404


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
            "/api/remote-ui/lyrics/v1/ui/home?x=1",
            headers={"Authorization": "Bearer test-token"},
        )

    assert resp.status_code == 200
    assert resp.json()["schema_version"] == 1
    call_kwargs = mock_client.request.await_args
    assert call_kwargs.args[0] == "GET"
    assert call_kwargs.args[1].startswith("http://127.0.0.1:8095/v1/ui/home")
    assert "x=1" in call_kwargs.args[1]


def test_proxy_upstream_timeout(client: TestClient) -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("t"))

    with patch("kb_app_api.routes.remote_ui.httpx.AsyncClient", return_value=mock_client):
        resp = client.get(
            "/api/remote-ui/lyrics/v1/ui/home",
            headers={"Authorization": "Bearer test-token"},
        )
    assert resp.status_code == 504
