#!/usr/bin/env python3
"""
Telegram notifications for knowledge-base-bot CI/CD (Mac mini deploy).

Secrets (GitHub Actions repository secrets or env on self-hosted runner):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

Optional:
  TELEGRAM_NOTIFY_DISABLED=1
  TELEGRAM_NOTIFY_PROXY=socks5://127.0.0.1:1080  (for api.telegram.org from RU)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def github_run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def git_short_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return os.environ.get("GITHUB_SHA", "")[:7] or "?"


def ci_context_lines() -> list[str]:
    lines: list[str] = []
    ref = os.environ.get("GITHUB_REF_NAME", "").strip()
    event = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    if ref:
        lines.append(f"Ветка: <code>{html_escape(ref)}</code>")
    if event:
        lines.append(f"Событие: <code>{html_escape(event)}</code>")
    lines.append(f"Коммит: <code>{html_escape(git_short_sha())}</code>")
    url = github_run_url()
    if url:
        lines.append(f'<a href="{html_escape(url)}">Workflow run</a>')
    return lines


def _telegram_form_data(chat_id: str, text: str) -> dict[str, str]:
    return {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }


def _socks_proxy_for_curl(proxy: str) -> str:
    # urllib.ProxyHandler не умеет SOCKS; curl — через socks5h (DNS через ss-local).
    if proxy.startswith("socks5://"):
        return "socks5h://" + proxy[len("socks5://") :]
    if proxy.startswith("socks://"):
        return "socks5h://" + proxy[len("socks://") :]
    return proxy


def _send_via_curl(url: str, data: dict[str, str], proxy: str) -> dict:
    args = ["curl", "-sfS", "--max-time", "45", "-X", "POST", url]
    if proxy:
        args.extend(["--proxy", _socks_proxy_for_curl(proxy)])
    for key, value in data.items():
        args.extend(["--data-urlencode", f"{key}={value}"])

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"curl failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if proc.returncode != 0:
        print(f"curl exit {proc.returncode}: {proc.stderr or proc.stdout}", file=sys.stderr)
        sys.exit(1)

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(f"Telegram API: invalid JSON: {proc.stdout!r}", file=sys.stderr)
        sys.exit(1)


def _send_via_urllib(url: str, data: dict[str, str], proxy: str | None) -> dict:
    payload = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")

    if proxy:
        handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})]
        opener = urllib.request.build_opener(*handlers)
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        print(f"Telegram API HTTP {exc.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Telegram API network error: {exc}", file=sys.stderr)
        sys.exit(1)


def send_telegram(text: str) -> None:
    if os.environ.get("TELEGRAM_NOTIFY_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        print("TELEGRAM_NOTIFY_DISABLED: skip")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set; skip notify")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = _telegram_form_data(chat_id, text)
    proxy = os.environ.get("TELEGRAM_NOTIFY_PROXY", "").strip()

    if proxy.startswith(("socks5://", "socks://")):
        body = _send_via_curl(url, data, proxy)
    else:
        body = _send_via_urllib(url, data, proxy or None)

    if not body.get("ok"):
        print(f"Telegram API error: {body}", file=sys.stderr)
        sys.exit(1)


def build_deploy_message(outcome: str) -> str:
    success = outcome == "success"
    title = (
        "✅ <b>Knowledge Base Bot — deploy на Mac mini</b>"
        if success
        else "❌ <b>Knowledge Base Bot — deploy не удался</b>"
    )
    lines = [title, "", *ci_context_lines()]
    if success:
        lines.extend(["", "Runtime обновлён: бот и KB App API на хосте, Docker-сервисы перезапущены."])
    else:
        lines.extend(["", "См. логи workflow на GitHub."])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram CI notifications for knowledge-base-bot")
    parser.add_argument("event", choices=["deploy"], help="Notification type")
    parser.add_argument(
        "--outcome",
        required=True,
        choices=["success", "failure", "cancelled", "skipped"],
        help="GitHub Actions step outcome",
    )
    args = parser.parse_args()

    if args.event == "deploy":
        message = build_deploy_message(args.outcome)

    send_telegram(message)
    print("Telegram notification sent.")


if __name__ == "__main__":
    main()
