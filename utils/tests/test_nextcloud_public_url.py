"""NEXTCLOUD_URL (API) vs NEXTCLOUD_WEB_URL (public links) rewrite."""
from services.nextcloud_service import rewrite_public_nextcloud_url


def test_rewrite_localhost_share_to_public_domain():
    out = rewrite_public_nextcloud_url(
        "http://127.0.0.1:8080/s/AbCdEfGh",
        "https://nextcloud.example.com",
    )
    assert out == "https://nextcloud.example.com/s/AbCdEfGh"


def test_rewrite_preserves_path_query():
    out = rewrite_public_nextcloud_url(
        "http://localhost/index.php/s/Token?foo=1",
        "https://nextcloud.example.ru",
    )
    assert out == "https://nextcloud.example.ru/index.php/s/Token?foo=1"


def test_public_share_unchanged():
    url = "https://nextcloud.example.com/s/AbCdEfGh"
    assert rewrite_public_nextcloud_url(url, "https://nextcloud.example.com") == url


def test_no_public_base_leaves_candidate():
    url = "http://127.0.0.1:8080/s/x"
    assert rewrite_public_nextcloud_url(url, None) == url
    assert rewrite_public_nextcloud_url(url, "") == url


def test_same_urls_no_op_when_already_public():
    """When API and WEB are both the public domain, nothing to rewrite."""
    url = "https://nextcloud.example.com/s/x"
    assert rewrite_public_nextcloud_url(url, "https://nextcloud.example.com") == url


def test_docker_internal_host_rewritten():
    out = rewrite_public_nextcloud_url(
        "http://host.docker.internal:8080/s/xyz",
        "https://nextcloud.example.com",
    )
    assert out == "https://nextcloud.example.com/s/xyz"
