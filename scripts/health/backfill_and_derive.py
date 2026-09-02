#!/usr/bin/env python3
"""Backfill линковки + пересчёт derived для локальной базы знаний."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_path() -> None:
    root = _repo_root()
    for pkg in ("health_linking", "health_aggregate"):
        p = str(root / "packages" / pkg)
        if p not in sys.path:
            sys.path.insert(0, p)


def main() -> int:
    _setup_path()
    from health_aggregate import refresh_derived
    from health_linking import backfill_all_linkable_workouts

    parser = argparse.ArgumentParser(description="Health backfill: link + derived")
    parser.add_argument(
        "--kb",
        default=os.getenv("LOCAL_KB_PATH", ""),
        help="Путь к корню vault (LOCAL_KB_PATH)",
    )
    parser.add_argument("--link-only", action="store_true")
    parser.add_argument("--derive-only", action="store_true")
    args = parser.parse_args()

    kb = Path(args.kb).expanduser().resolve() if args.kb else None
    if not kb or not kb.is_dir():
        print("Укажите --kb или LOCAL_KB_PATH", file=sys.stderr)
        return 1

    if not args.derive_only:
        result = backfill_all_linkable_workouts(kb)
        print(f"Linked: {len(result.linked)}")
        for item in result.linked:
            print(f"  + {item}")
        if result.skipped:
            print(f"Skipped: {len(result.skipped)}")
        if result.errors:
            print(f"Errors: {result.errors}", file=sys.stderr)

    if not args.link_only:
        summary = refresh_derived(kb)
        print(
            f"Derived refreshed: {summary.get('daily_files_count')} daily files, "
            f"reference {summary.get('reference_date')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
