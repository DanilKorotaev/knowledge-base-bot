"""Tests for allowlisted absolute-URL remote-ui proxy."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

_db: str | None = None
_kb: str | None = None


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    global _db, _kb
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db = path
    _kb = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db
    os.environ["LOCAL_KB_PATH"] = _kb
    os.environ["KB_APP_JWT_SECRET"] = "remote-ui-jwt"
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ["ACCESS_MODE"] = "open"

    import config as config_mod
    from utils import db_helpers

    config_mod.config.KB_APP_JWT_SECRET = "remote-ui-jwt"
    config_mod.config.KB_APP_OPEN_SIGNUP = True
    config_mod.config.KB_APP_NC_PROVISION_ENABLED = False
    config_mod.config.REMOTE_UI_HOST_ALLOWLIST = ["127.0.0.1", "localhost"]
    config_mod.config.REMOTE_UI_ALLOWED_SCHEMES = ["http", "https"]
    config_mod.config.DB_TYPE = "sqlite"
    config_mod.config.DB_FILE = _db
    config_mod.config.LOCAL_KB_PATH = Path(_kb)
    config_mod.config.ACCESS_MODE = "open"
    db_helpers._db_instance = None  # type: ignore[attr-defined]

    from kb_app_api.main import app
    from kb_app_api.tests.auth_test_helpers import bearer_headers

    tc = TestClient(app)
    # stash auth headers on client for tests
    tc.auth_headers = bearer_headers(tc, login="remoteui")  # type: ignore[attr-defined]
    return tc


def test_allowlist(client: TestClient) -> None:
    resp = client.get(
        "/api/remote-ui/allowlist",
        headers=client.auth_headers,  # type: ignore[attr-defined]
    )
    assert resp.status_code == 200
    assert "127.0.0.1" in resp.json()["hosts"]


def test_host_forbidden(client: TestClient) -> None:
    resp = client.get(
        "/api/remote-ui",
        params={"url": "http://evil.example/v1/ui/home"},
        headers=client.auth_headers,  # type: ignore[attr-defined]
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
            headers=client.auth_headers,  # type: ignore[attr-defined]
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
            headers=client.auth_headers,  # type: ignore[attr-defined]
        )
    assert resp.status_code == 504
