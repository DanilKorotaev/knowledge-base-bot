"""nextcloud:// open-file deep link builder (no live Nextcloud)."""
from urllib.parse import parse_qs, urlparse

from services.nextcloud_service import NextCloudService


def _svc(**kwargs) -> NextCloudService:
    svc = NextCloudService.__new__(NextCloudService)
    svc.web_url = kwargs.get("web_url", "https://nextcloud.coredan.ru")
    svc.url = kwargs.get("url", "http://host.docker.internal:8080")
    svc.base_path = kwargs.get("base_path", "KnowledgeBase")
    svc.deeplink_username = kwargs.get("deeplink_username", "danilpdr")
    svc.username = kwargs.get("username", "telegram_knowledge_bot")
    return svc


def test_build_nextcloud_deeplink_encodes_spaces_as_percent20():
    link = _svc().build_nextcloud_deeplink("docs/my plan.md")
    assert link is not None
    assert link.startswith("nextcloud://open-file?")
    assert "+" not in link.split("path=", 1)[-1].split("&")[0]
    qs = parse_qs(urlparse(link).query)
    assert qs["user"] == ["danilpdr"]
    assert qs["link"] == ["https://nextcloud.coredan.ru"]
    assert qs["path"] == ["KnowledgeBase/docs/my plan.md"]


def test_build_nextcloud_deeplink_prefers_file_id():
    link = _svc().build_nextcloud_deeplink("docs/x.md", file_id=210190)
    assert link == "nextcloud://directlink/f/210190"


def test_build_nextcloud_deeplink_requires_user_and_base():
    assert _svc(web_url=None, url=None).build_nextcloud_deeplink("x.md") is None
    assert _svc(deeplink_username="").build_nextcloud_deeplink("x.md") is None
