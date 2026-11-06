"""Render assistant markdown for the public share HTML viewer (XSS-hardened)."""
from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import urlparse

_MD_EXTENSIONS = ["fenced_code", "tables", "nl2br", "sane_lists"]

# Tags produced by python-markdown for typical chat content.
_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "em",
        "b",
        "i",
        "code",
        "pre",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "blockquote",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "span",
    }
)
_ALLOWED_ATTRS = {
    "a": frozenset({"href", "title", "rel", "target"}),
    "code": frozenset({"class"}),
    "pre": frozenset({"class"}),
    "th": frozenset({"align"}),
    "td": frozenset({"align"}),
    "span": frozenset({"class"}),
}

_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)([^>]*)>|([^<]+)", re.DOTALL)
_ATTR_RE = re.compile(
    r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))""",
    re.DOTALL,
)


def _safe_href(value: str) -> str | None:
    href = (value or "").strip()
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme.lower() in {"http", "https"}:
        return href
    if not parsed.scheme and href.startswith("/"):
        return href
    return None


def _sanitize_fragment(fragment: str) -> str:
    """Keep an allowlist of tags/attrs; drop the rest (text preserved)."""
    out: list[str] = []
    for match in _TAG_RE.finditer(fragment):
        tag_name, attrs_raw, text = match.group(1), match.group(2), match.group(3)
        if text is not None:
            out.append(text)
            continue
        assert tag_name is not None
        name = tag_name.lower()
        raw = match.group(0)
        is_close = raw.startswith("</")
        if name not in _ALLOWED_TAGS:
            continue
        if is_close:
            out.append(f"</{name}>")
            continue
        self_closing = raw.rstrip().endswith("/>") or name == "br" or name == "hr"
        allowed = _ALLOWED_ATTRS.get(name, frozenset())
        kept: list[str] = []
        for attr_match in _ATTR_RE.finditer(attrs_raw or ""):
            attr = attr_match.group(1).lower()
            if attr not in allowed:
                continue
            value = attr_match.group(3) or attr_match.group(4) or attr_match.group(5) or ""
            if attr == "href":
                safe = _safe_href(value)
                if not safe:
                    continue
                kept.append(f'href="{html.escape(safe, quote=True)}"')
                kept.append('rel="noopener noreferrer"')
                kept.append('target="_blank"')
                continue
            if attr.startswith("on") or "javascript:" in value.lower():
                continue
            kept.append(f'{attr}="{html.escape(value, quote=True)}"')
        attr_str = (" " + " ".join(kept)) if kept else ""
        if self_closing and name in {"br", "hr"}:
            out.append(f"<{name}{attr_str}>")
        else:
            out.append(f"<{name}{attr_str}>")
    return "".join(out)


def markdown_to_share_html(text: str) -> str:
    """Convert chat markdown to sanitized HTML for the public share page."""
    source = (text or "").strip("\n")
    if not source:
        return ""
    try:
        import markdown as md
    except ImportError:  # pragma: no cover — requirements pin Markdown
        return html.escape(source).replace("\n", "<br>")

    rendered = md.markdown(source, extensions=_MD_EXTENSIONS)
    return _sanitize_fragment(rendered)


def share_role_label(message: dict[str, Any]) -> str:
    """Human-readable sender label for the public share HTML viewer."""
    role = str(message.get("role") or "user")
    if role == "assistant":
        return "Ассистент"
    if role == "external":
        external = message.get("external") if isinstance(message.get("external"), dict) else {}
        participant = external.get("participant") if isinstance(external.get("participant"), dict) else {}
        label = str(participant.get("label") or "").strip()
        if label:
            return label
        source = str(external.get("source") or message.get("source") or "").strip()
        return source or "Внешний источник"
    if role == "system":
        return "Система"
    return "Вы"


def render_share_external_body(message: dict[str, Any]) -> str:
    """Summary + optional expandable detail/links for role=external on share page."""
    external = message.get("external") if isinstance(message.get("external"), dict) else {}
    summary = str(
        external.get("summary") or message.get("content") or "External event"
    ).strip()
    parts = [f'<div class="ext-summary">{html.escape(summary).replace(chr(10), "<br>")}</div>']

    detail = external.get("detail")
    if detail is not None and str(detail).strip():
        detail_html = html.escape(str(detail)).replace("\n", "<br>")
        parts.append(
            "<details class=\"ext-detail\">"
            "<summary>Подробности</summary>"
            f'<div class="ext-detail-body">{detail_html}</div>'
            "</details>"
        )

    links = external.get("links") if isinstance(external.get("links"), list) else []
    link_items: list[str] = []
    for link in links[:20]:
        if not isinstance(link, dict):
            continue
        url = str(link.get("url") or "").strip()
        if not url:
            continue
        title = str(link.get("title") or url).strip() or url
        # Reuse markdown sanitizer policy: only http(s).
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        link_items.append(
            f'<li><a href="{html.escape(url, quote=True)}" rel="noopener noreferrer" '
            f'target="_blank">{html.escape(title)}</a></li>'
        )
    if link_items:
        parts.append('<ul class="ext-links">' + "".join(link_items) + "</ul>")

    return "".join(parts)


def render_share_message_body(message: dict[str, Any]) -> str:
    """Pick plain vs markdown rendering for one shared message bubble."""
    role = str(message.get("role") or "user")
    content = str(message.get("content") or "")
    fmt = str(message.get("content_format") or "").lower()

    if role == "external":
        return render_share_external_body(message)

    if role == "assistant" or fmt == "markdown":
        body = markdown_to_share_html(content)
        if body:
            return body
        return ""

    # User / system: keep as escaped plain text with line breaks.
    return html.escape(content).replace("\n", "<br>")
