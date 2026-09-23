"""Read-only car-expenses (fuel) board compute from vault markdown.

Scans fuel notes with YAML ``type: fuel`` under a configurable folder.
Does not create, update, or delete any vault files.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from kb_app_api.boards.vault_io import VaultReadError, iter_markdown_files, resolve_under_root

logger = logging.getLogger(__name__)

BOARD_ID = "car-fuel"
DEFAULT_FUEL_RELATIVE = "Документы/Тачки/Соляра/Расходы/Топливо"
_WIKILINK_RE = re.compile(r"^\[\[(.+?)\]\]$")


@dataclass(frozen=True)
class FuelEntry:
    date: date
    cost: float
    liters: float | None
    station: str
    fuel_type: str
    path: str


def fuel_folder_relative() -> str:
    return os.getenv("BOARDS_CAR_FUEL_RELATIVE", DEFAULT_FUEL_RELATIVE).strip() or DEFAULT_FUEL_RELATIVE


def _clean_wikilink(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    match = _WIKILINK_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _format_money(amount: float) -> str:
    rounded = round(amount)
    if abs(amount - rounded) < 0.005:
        return f"{rounded:,}".replace(",", " ")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def _format_liters(liters: float | None) -> str:
    if liters is None:
        return "—"
    if abs(liters - round(liters)) < 0.005:
        return str(int(round(liters)))
    return f"{liters:.2f}".rstrip("0").rstrip(".")


def load_fuel_entries(kb_root: Path, relative_dir: str | None = None) -> list[FuelEntry]:
    """Read fuel notes from disk. Never writes."""
    folder = relative_dir or fuel_folder_relative()
    try:
        files = iter_markdown_files(kb_root, folder)
    except VaultReadError:
        logger.warning("fuel folder escapes KB root: %s", folder)
        return []

    entries: list[FuelEntry] = []
    root = kb_root.resolve()
    for path in files:
        try:
            # Read-only open via frontmatter helper (file opened for reading).
            with path.open("r", encoding="utf-8") as handle:
                post = frontmatter.load(handle)
        except OSError as exc:
            logger.warning("skip unreadable fuel note %s: %s", path, exc)
            continue
        except Exception as exc:  # noqa: BLE001 — bad YAML should not break the board
            logger.warning("skip unparseable fuel note %s: %s", path, exc)
            continue

        meta = post.metadata or {}
        note_type = str(meta.get("type") or "").strip().lower()
        if note_type != "fuel":
            continue
        note_date = _parse_date(meta.get("date"))
        cost = _parse_float(meta.get("cost"))
        if note_date is None or cost is None:
            continue
        liters = _parse_float(meta.get("liters"))
        try:
            rel = str(path.resolve().relative_to(root))
        except ValueError:
            rel = path.name
        entries.append(
            FuelEntry(
                date=note_date,
                cost=cost,
                liters=liters,
                station=_clean_wikilink(meta.get("station")),
                fuel_type=_clean_wikilink(meta.get("fuel_type")),
                path=rel,
            )
        )

    entries.sort(key=lambda e: (e.date, e.path), reverse=True)
    return entries


def _month_total(entries: list[FuelEntry], today: date) -> float:
    return sum(e.cost for e in entries if e.date.year == today.year and e.date.month == today.month)


def build_car_fuel_document(
    entries: list[FuelEntry],
    *,
    today: date | None = None,
    recent_limit: int = 10,
) -> dict[str, Any]:
    today = today or date.today()
    total = sum(e.cost for e in entries)
    month = _month_total(entries, today)
    last = entries[0] if entries else None
    recent = entries[:recent_limit]

    metrics_children: list[dict[str, Any]] = [
        {
            "type": "metric",
            "id": "m_month",
            "label": "Этот месяц",
            "text": f"{_format_money(month)} ₽",
        },
        {
            "type": "metric",
            "id": "m_total",
            "label": "Всего топливо",
            "text": f"{_format_money(total)} ₽",
        },
        {
            "type": "metric",
            "id": "m_last",
            "label": "Последняя",
            "text": f"{_format_money(last.cost)} ₽" if last else "—",
        },
        {
            "type": "metric",
            "id": "m_count",
            "label": "Заправок",
            "text": str(len(entries)),
        },
    ]

    rows = [
        [
            e.date.isoformat(),
            e.station or "—",
            _format_liters(e.liters),
            f"{_format_money(e.cost)} ₽",
        ]
        for e in recent
    ]

    children: list[dict[str, Any]] = [
        {"type": "text", "id": "title", "text": "Соляра — топливо"},
        {
            "type": "callout",
            "id": "readonly",
            "text": "Сводка только читает заметки из vault. Файлы не изменяются.",
            "variant": "info",
        },
        {
            "type": "hstack",
            "id": "metrics_row",
            "spacing": 12,
            "children": metrics_children,
        },
    ]

    if last:
        children.append(
            {
                "type": "callout",
                "id": "last_detail",
                "text": (
                    f"Последняя: {last.date.isoformat()}"
                    + (f", {last.station}" if last.station else "")
                    + (f", {_format_liters(last.liters)} л" if last.liters is not None else "")
                ),
                "variant": "tip",
            }
        )

    children.append(
        {
            "type": "table",
            "id": "recent_fuel",
            "label": f"Последние {len(recent)} заправок",
            "columns": [
                {"id": "date", "label": "Дата"},
                {"id": "station", "label": "АЗС"},
                {"id": "liters", "label": "Л"},
                {"id": "cost", "label": "Сумма"},
            ],
            "rows": rows,
        }
    )

    return {"schema_version": 1, "screen": {"type": "vstack", "id": "root", "children": children}}


def build_car_fuel_list_cell(entries: list[FuelEntry], *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    month = _month_total(entries, today)
    last = entries[0] if entries else None
    return {
        "kind": "metrics",
        "title": "Авторасходы — топливо",
        "subtitle": "Соляра · только чтение",
        "metrics": [
            {"label": "Месяц", "value": f"{_format_money(month)} ₽"},
            {
                "label": "Последняя",
                "value": f"{_format_money(last.cost)} ₽" if last else "—",
            },
        ],
    }


def compute_car_fuel_board(kb_root: Path) -> dict[str, Any]:
    """Return board + document payload; read-only against ``kb_root``."""
    # Ensure configured folder cannot escape root (raises if bad config).
    try:
        resolve_under_root(kb_root, fuel_folder_relative())
    except VaultReadError as exc:
        logger.error("car fuel board path invalid: %s", exc)
        entries: list[FuelEntry] = []
    else:
        entries = load_fuel_entries(kb_root)

    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    board = {
        "id": BOARD_ID,
        "title": "Авторасходы — топливо",
        "subtitle": "Соляра · только чтение",
        "icon": "fuelpump",
        "kind": "cached_view",
        "sort_order": 5,
        "enabled": True,
        "list_cell": build_car_fuel_list_cell(entries),
        "rendered_at": rendered_at,
    }
    return {
        "board": board,
        "document": build_car_fuel_document(entries),
        "rendered_at": rendered_at,
    }
