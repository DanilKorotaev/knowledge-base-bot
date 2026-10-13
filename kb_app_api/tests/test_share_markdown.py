"""Unit tests for public share markdown → HTML rendering."""
from __future__ import annotations

import unittest

from kb_app_api.share_markdown import markdown_to_share_html, render_share_message_body


class TestShareMarkdown(unittest.TestCase):
    def test_bold_code_and_list(self) -> None:
        html = markdown_to_share_html("**bold** and `x`\n\n- a\n- b")
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>x</code>", html)
        self.assertIn("<li>", html)

    def test_strips_raw_script_from_markdown_html(self) -> None:
        html = markdown_to_share_html('<script>alert(1)</script>\n\n**ok**')
        self.assertNotIn("<script>", html.lower())
        self.assertIn("<strong>ok</strong>", html)

    def test_blocks_javascript_links(self) -> None:
        html = markdown_to_share_html("[x](javascript:alert(1))")
        self.assertNotIn("javascript:", html.lower())

    def test_allows_https_links(self) -> None:
        html = markdown_to_share_html("[docs](https://example.com/a)")
        self.assertIn('href="https://example.com/a"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_user_message_stays_plain(self) -> None:
        body = render_share_message_body(
            {"role": "user", "content": "**not markdown**\nline2"}
        )
        self.assertIn("**not markdown**", body)
        self.assertIn("<br>", body)
        self.assertNotIn("<strong>", body)

    def test_assistant_uses_markdown(self) -> None:
        body = render_share_message_body(
            {"role": "assistant", "content": "Hello **world**"}
        )
        self.assertIn("<strong>world</strong>", body)


if __name__ == "__main__":
    unittest.main()
