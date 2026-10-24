"""nextcloud:// open-file deep link builder (matches current nextcloud/ios SceneDelegate)."""
from urllib.parse import parse_qs, unquote, urlparse

from services.nextcloud_service import NextCloudService


def _svc(**kwargs) -> NextCloudService:
    svc = NextCloudService.__new__(NextCloudService)
    svc.web_url = kwargs.get("web_url", "https://nextcloud.coredan.ru")
    svc.url = kwargs.get("url", "http://127.0.0.1:8080")
    svc.base_path = kwargs.get("base_path", "KnowledgeBase")
    svc.deeplink_username = kwargs.get("deeplink_username", "danilpdr")
    svc.username = kwargs.get("username", "telegram_knowledge_bot")
    return svc


def test_web_url_uses_index_php_f():
    assert _svc().get_web_url("x.md", file_id=152680) == (
        "https://nextcloud.coredan.ru/index.php/f/152680"
    )


def test_web_url_fallback_uses_index_php_apps_files():
    url = _svc().get_web_url("Питание/Дневник/2026/2026-10-23.md")
    assert url.startswith("https://nextcloud.coredan.ru/index.php/apps/files/?")
    assert "dir=" in url and "scrollto=" in url


def test_build_nextcloud_deeplink_puts_file_url_in_link_param():
    link = _svc().build_nextcloud_deeplink("docs/x.md", file_id=152680)
    assert link is not None
    assert link.startswith("nextcloud://open-file?")
    qs = parse_qs(urlparse(link).query)
    assert qs["user"] == ["danilpdr"]
    assert unquote(qs["link"][0]) == "https://nextcloud.coredan.ru/index.php/f/152680"
    assert "path" not in qs


def test_build_nextcloud_deeplink_requires_file_id():
    assert _svc().build_nextcloud_deeplink("docs/x.md") is None
    assert _svc(deeplink_username="").build_nextcloud_deeplink("x.md", file_id=1) is None
