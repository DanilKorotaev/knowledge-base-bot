"""Telegram ↔ app user link and session focus (sqlite, no Nextcloud)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_db_file: str | None = None
_kb_dir: str | None = None


def setUpModule() -> None:
    global _db_file, _kb_dir
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    _db_file = path
    _kb_dir = tempfile.mkdtemp()
    os.environ["DB_TYPE"] = "sqlite"
    os.environ["DB_FILE"] = _db_file
    os.environ["KB_APP_JWT_SECRET"] = "tg-link-jwt"
    os.environ["KB_APP_OPEN_SIGNUP"] = "true"
    os.environ["KB_APP_NC_PROVISION_ENABLED"] = "false"
    os.environ["ACCESS_MODE"] = "open"
    os.environ["LOCAL_KB_PATH"] = _kb_dir
    from config import config

    config.DB_TYPE = "sqlite"
    config.DB_FILE = _db_file
    config.KB_APP_JWT_SECRET = "tg-link-jwt"
    config.KB_APP_OPEN_SIGNUP = True
    config.KB_APP_NC_PROVISION_ENABLED = False
    config.ACCESS_MODE = "open"
    config.LOCAL_KB_PATH = Path(_kb_dir)
    import utils.db_helpers as db_helpers

    db_helpers._db_instance = None


def tearDownModule() -> None:
    if _db_file and os.path.isfile(_db_file):
        try:
            os.unlink(_db_file)
        except OSError:
            pass


@unittest.skipUnless(TestClient is not None, "fastapi required")
class TestTelegramLink(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app

        cls.client = TestClient(app)

    def _register(self, login: str) -> dict:
        response = self.client.post(
            "/api/auth/register",
            json={"login": login, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_link_me_and_conflict(self) -> None:
        alice = self._register("tg-alice")
        headers = {"Authorization": f"Bearer {alice['access_token']}"}
        me = self.client.get("/api/auth/me", headers=headers)
        self.assertFalse(me.json()["user"]["telegram_linked"])
        self.assertIsNone(me.json()["user"]["telegram_id"])

        started = self.client.post("/api/auth/telegram/link", headers=headers)
        self.assertEqual(started.status_code, 200, started.text)
        code = started.json()["code"]
        self.assertTrue(started.json()["command"].endswith(code))

        import asyncio

        from kb_app_api.telegram_link import accept_link_code
        from utils.db_helpers import get_db

        async def _accept(token: str, telegram_id: int) -> None:
            db = await get_db()
            await accept_link_code(db, token, telegram_id, "alice")

        asyncio.run(_accept(code, 424242))
        me = self.client.get("/api/auth/me", headers=headers)
        user = me.json()["user"]
        self.assertTrue(user["telegram_linked"])
        self.assertEqual(user["telegram_id"], 424242)
        self.assertEqual(user["telegram_username"], "alice")

        bob = self._register("tg-bob")
        bob_headers = {"Authorization": f"Bearer {bob['access_token']}"}
        bob_code = self.client.post("/api/auth/telegram/link", headers=bob_headers).json()["code"]

        async def _conflict() -> None:
            db = await get_db()
            await accept_link_code(db, bob_code, 424242, "bob")

        from kb_app_api.errors import APIError

        with self.assertRaises(APIError) as caught:
            asyncio.run(_conflict())
        self.assertEqual(caught.exception.status_code, 409)

        async def _reuse_raises() -> None:
            db = await get_db()
            await accept_link_code(db, code, 424242, "alice")

        with self.assertRaises(APIError):
            asyncio.run(_reuse_raises())

        deleted = self.client.delete("/api/auth/telegram/link", headers=headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertFalse(deleted.json()["user"]["telegram_linked"])

    def test_same_telegram_links_to_new_user_after_unlink(self) -> None:
        import asyncio

        from kb_app_api.telegram_link import accept_link_code, preview_link_code
        from utils.db_helpers import get_db

        first = self._register("tg-old")
        first_headers = {"Authorization": f"Bearer {first['access_token']}"}
        first_code = self.client.post("/api/auth/telegram/link", headers=first_headers).json()["code"]

        async def _accept(token: str, telegram_id: int, username: str) -> None:
            db = await get_db()
            await accept_link_code(db, token, telegram_id, username)

        asyncio.run(_accept(first_code, 616161, "old"))
        freed = self.client.delete("/api/auth/telegram/link", headers=first_headers)
        self.assertEqual(freed.status_code, 200, freed.text)
        self.assertFalse(freed.json()["user"]["telegram_linked"])

        second = self._register("tg-new")
        second_headers = {"Authorization": f"Bearer {second['access_token']}"}
        second_code = self.client.post("/api/auth/telegram/link", headers=second_headers).json()["code"]

        async def _preview() -> dict:
            db = await get_db()
            return await preview_link_code(db, second_code, 616161)

        preview = asyncio.run(_preview())
        self.assertEqual(preview["status"], "ready")
        self.assertEqual(preview["login"], "tg-new")
        still = self.client.get("/api/auth/me", headers=second_headers)
        self.assertFalse(still.json()["user"]["telegram_linked"])

        asyncio.run(_accept(second_code, 616161, "new"))
        moved = self.client.get("/api/auth/me", headers=second_headers)
        self.assertTrue(moved.json()["user"]["telegram_linked"])
        self.assertEqual(moved.json()["user"]["telegram_id"], 616161)
        old = self.client.get("/api/auth/me", headers=first_headers)
        self.assertFalse(old.json()["user"]["telegram_linked"])

    def test_webapp_init_data_becomes_jwt(self) -> None:
        import hashlib
        import hmac
        import json
        import time
        from urllib.parse import urlencode

        from config import config

        config.TELEGRAM_TOKEN = "test-token"
        registered = self._register("tg-web")
        headers = {"Authorization": f"Bearer {registered['access_token']}"}
        code = self.client.post("/api/auth/telegram/link", headers=headers).json()["code"]

        import asyncio

        from kb_app_api.telegram_link import accept_link_code
        from utils.db_helpers import get_db

        async def _bind() -> None:
            db = await get_db()
            await accept_link_code(db, code, 909090, "web")

        asyncio.run(_bind())

        user = json.dumps({"id": 909090, "username": "web"}, separators=(",", ":"))
        fields = {"auth_date": str(int(time.time())), "user": user}
        check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.new(b"WebAppData", b"test-token", hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        init_data = urlencode(fields)

        denied_user = json.dumps({"id": 111, "username": "nope"}, separators=(",", ":"))
        denied_fields = {"auth_date": fields["auth_date"], "user": denied_user}
        denied_check = "\n".join(f"{key}={denied_fields[key]}" for key in sorted(denied_fields))
        denied_fields["hash"] = hmac.new(secret, denied_check.encode(), hashlib.sha256).hexdigest()
        unlinked = self.client.post(
            "/api/auth/telegram/webapp",
            json={"init_data": urlencode(denied_fields)},
        )
        self.assertEqual(unlinked.status_code, 403, unlinked.text)
        self.assertIn("привяз", unlinked.json()["error"]["message"])

        exchanged = self.client.post("/api/auth/telegram/webapp", json={"init_data": init_data})
        self.assertEqual(exchanged.status_code, 200, exchanged.text)
        body = exchanged.json()
        self.assertTrue(body["access_token"])
        self.assertEqual(body["user"]["login"], "tg-web")
        self.assertTrue(body["user"]["telegram_linked"])
        me = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        self.assertEqual(me.status_code, 200, me.text)

    def test_new_telegram_chat_keeps_app_session(self) -> None:
        import asyncio

        from kb_app_api.telegram_link import accept_link_code
        from services.session_service import SessionService
        from utils.constants import SessionStatus
        from utils.db_helpers import get_db

        cara = self._register("tg-cara")
        headers = {"Authorization": f"Bearer {cara['access_token']}"}
        created = self.client.post(
            "/api/sessions",
            headers=headers,
            json={"title": "С телефона"},
        )
        self.assertEqual(created.status_code, 201, created.text)
        app_session_id = int(created.json()["session"]["id"])
        code = self.client.post("/api/auth/telegram/link", headers=headers).json()["code"]

        async def _run() -> str:
            db = await get_db()
            await accept_link_code(db, code, 515151, "cara")
            session = await SessionService().create_new_session(515151, "cara")
            app_session = await db.get_session(app_session_id)
            focused = await db.get_active_session(int(app_session["user_id"]))
            self.assertEqual(str(app_session["status"]), str(SessionStatus.ACTIVE))
            self.assertIsNotNone(focused)
            self.assertNotEqual(int(focused["id"]), app_session_id)
            self.assertEqual(int(focused["id"]), int(session["id"]))
            return str(app_session["status"])

        asyncio.run(_run())


@unittest.skipUnless(TestClient is not None, "fastapi required")
class TestMiniAppVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from kb_app_api.main import app as kb_app
        from miniapp.api.main import app as mini_app

        cls.kb = TestClient(kb_app)
        cls.mini_app = mini_app
        cls.mini = TestClient(mini_app)

    def tearDown(self) -> None:
        self.mini_app.dependency_overrides.clear()

    def _init_headers(self, telegram_id: int) -> dict[str, str]:
        import hashlib
        import hmac
        import json
        import time
        from urllib.parse import urlencode

        from config import config

        user = json.dumps({"id": telegram_id, "username": "tester"}, separators=(",", ":"))
        fields = {"auth_date": str(int(time.time())), "user": user}
        check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
        secret = hmac.new(b"WebAppData", (config.TELEGRAM_TOKEN or "").encode(), hashlib.sha256).digest()
        fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        return {"X-Telegram-Init-Data": urlencode(fields)}

    def test_unlinked_does_not_create_user_and_files_stay_in_vault(self) -> None:
        import asyncio
        from pathlib import Path

        from kb_app_api.telegram_link import accept_link_code
        from kb_app_api.vault_paths import absolute_vault_root
        from utils.db_helpers import get_db

        denied = self.mini.get("/api/sessions", headers=self._init_headers(777001))
        self.assertEqual(denied.status_code, 403, denied.text)
        self.assertIn("привяз", denied.json()["detail"])

        async def _no_row() -> None:
            db = await get_db()
            self.assertIsNone(await db.get_user_by_telegram_id(777001))

        asyncio.run(_no_row())

        registered = self.kb.post(
            "/api/auth/register",
            json={"login": "mini-dana", "password": "password123"},
        )
        self.assertEqual(registered.status_code, 200, registered.text)
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
        code = self.kb.post("/api/auth/telegram/link", headers=headers).json()["code"]

        async def _bind() -> dict:
            db = await get_db()
            return await accept_link_code(db, code, 888002, "dana")

        user = asyncio.run(_bind())
        vault = absolute_vault_root(user)
        (vault / "note.md").write_text("mine", encoding="utf-8")
        outside = Path(_kb_dir) / "secret.md"
        outside.write_text("nope", encoding="utf-8")

        headers = self._init_headers(888002)
        listed = self.mini.get("/api/files/list", params={"path": ""}, headers=headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        names = [item["name"] for item in listed.json()["items"]]
        self.assertIn("note.md", names)
        self.assertNotIn("secret.md", names)

        opened = self.mini.get("/api/files/view", params={"path": "note.md"}, headers=headers)
        self.assertEqual(opened.status_code, 200, opened.text)
        self.assertEqual(opened.json()["content"], "mine")

        escaped = self.mini.get(
            "/api/files/view", params={"path": "../../secret.md"}, headers=headers
        )
        self.assertEqual(escaped.status_code, 403, escaped.text)


class TestTelegramMarkdown(unittest.TestCase):
    def test_code_paths_keep_underscores(self) -> None:
        from utils.message_helpers import markdown_to_html

        html_text = markdown_to_html("Файл `Питание/foo_bar.md` и **жирный**")
        self.assertIn("<code>Питание/foo_bar.md</code>", html_text)
        self.assertIn("<b>жирный</b>", html_text)
        self.assertNotIn("<i>", html_text.split("<code>")[0])
