#!/usr/bin/env python3
"""
POST CI/CD events to KB App per-user ingress.

Secrets / env (prefer one full URL — domain + path + token):
  KBAPP_INGRESS_URL   e.g. https://kbapp.example/api/ingress/<token>

Optional:
  KBAPP_INGRESS_DISABLED=1
  KBAPP_INGRESS_SOURCE=github_actions   (default)
  HTTP(S)_PROXY / ALL_PROXY            (if needed from the runner)

Body shape is fixed here; routing/rules live in the API (per-user config).
Does not replace Telegram notify — call both from the workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def github_run_url() -> str | None:
    server = _env("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = _env("GITHUB_REPOSITORY")
    run_id = _env("GITHUB_RUN_ID")
    if repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def git_commit_message() -> str:
    sha = _env("GITHUB_SHA")
    if not sha:
        return ""
    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--pretty=%B", sha],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


def post_json(url: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            print(f"ingress HTTP {response.status}: {body[:500]}")
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"ingress HTTP {exc.code}: {err}", file=sys.stderr)
        # Do not fail the workflow solely because ingress is misconfigured.
        sys.exit(0)
    except urllib.error.URLError as exc:
        print(f"ingress URL error: {exc}", file=sys.stderr)
        sys.exit(0)


def build_envelope(
    *,
    kind: str,
    outcome: str,
    failed_tests: list[str] | None = None,
) -> dict:
    source = _env("KBAPP_INGRESS_SOURCE", "github_actions")
    repo = _env("GITHUB_REPOSITORY") or "unknown"
    ref = _env("GITHUB_REF_NAME")
    sha = _env("GITHUB_SHA")
    run_url = github_run_url()
    commit_message = git_commit_message()
    ok = outcome == "success"
    event_type = f"ci.{kind}_{'succeeded' if ok else 'failed'}"
    summary = f"{repo}: {kind} {'OK' if ok else 'FAILED'}"
    if ref:
        summary = f"{summary} ({ref})"

    detail_parts = [
        f"repository: {repo}",
        f"kind: {kind}",
        f"outcome: {outcome}",
        f"ref: {ref or '-'}",
        f"sha: {sha or '-'}",
    ]
    if run_url:
        detail_parts.append(f"run: {run_url}")
    if failed_tests:
        detail_parts.append("failed_tests:")
        detail_parts.extend(f"- {name}" for name in failed_tests[:40])

    dedupe = _env("GITHUB_RUN_ID") or sha or "local"
    links = []
    if run_url:
        links.append({"title": "Workflow run", "url": run_url})

    return {
        "source": source,
        "type": event_type,
        "summary": summary,
        "detail": "\n".join(detail_parts),
        "hints": {
            "commit_sha": sha,
            "commit_message": commit_message,
            "repository": repo,
            "ref": ref,
            "workflow": _env("GITHUB_WORKFLOW"),
            "run_id": _env("GITHUB_RUN_ID"),
            "kind": kind,
            "outcome": outcome,
        },
        "payload": {
            "failed_tests": failed_tests or [],
            "outcome": outcome,
            "kind": kind,
        },
        "links": links,
        "dedupe_key": f"gha:{repo}:{kind}:{dedupe}:{outcome}",
        "adapter_key": "github_actions",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Notify KB App ingress from CI")
    parser.add_argument("kind", choices=["tests", "deploy", "testflight", "build"])
    parser.add_argument("--outcome", required=True)
    parser.add_argument(
        "--failed-test",
        action="append",
        default=[],
        help="Optional failed test identifier (repeatable)",
    )
    args = parser.parse_args()

    if _env("KBAPP_INGRESS_DISABLED") in ("1", "true", "yes"):
        print("KBAPP_INGRESS_DISABLED: skip")
        return

    url = _env("KBAPP_INGRESS_URL")
    if not url:
        print("KBAPP_INGRESS_URL not set; skip ingress notify")
        return

    envelope = build_envelope(
        kind=args.kind,
        outcome=args.outcome,
        failed_tests=list(args.failed_test or []),
    )
    post_json(url, envelope)


if __name__ == "__main__":
    main()
