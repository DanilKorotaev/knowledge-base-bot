"""Generic read-only vault frontmatter aggregation provider.

Paths and filters come from the board ``definition`` JSON (DB), not from app code.
Never writes vault files.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

from kb_app_api.boards.vault_io import VaultReadError, iter_markdown_files, resolve_under_root

logger = logging.getLogger(__name__)

PROVIDER_ID = "vault_frontmatter_agg"
_WIKILINK_RE = re.compile(r"^\[\[(.+?)\]\]$")


@dataclass(frozen=True)
class AggEntry:
    date: date
    amount: float
    quantity: float | None
    label: str
    path: str


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


def _format_qty(qty: float | None) -> str:
    if qty is None:
        return "—"
    if abs(qty - round(qty)) < 0.005:
        return str(int(round(qty)))
    return f"{qty:.2f}".rstrip("0").rstrip(".")


def _meta_get(meta: dict[str, Any], dotted: str) -> Any:
    """Read ``a.b.c`` from nested frontmatter dicts; flat keys work too."""
    current: Any = meta
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _filter_matches(meta: dict[str, Any], filt: dict[str, Any]) -> bool:
    """Equality filters on frontmatter; ``type`` compared case-insensitively."""
    for key, expected in filt.items():
        raw = meta.get(key)
        if key == "type":
            if str(raw or "").strip().lower() != str(expected or "").strip().lower():
                return False
            continue
        if str(raw if raw is not None else "").strip().lower() != str(expected).strip().lower():
            return False
    return True


def load_entries(kb_root: Path, definition: dict[str, Any]) -> list[AggEntry]:
    """Read matching notes under ``definition.path``. Never writes."""
    relative = str(definition.get("path") or "").strip()
    if not relative:
        return []
    filt = definition.get("filter") or {}
    if not isinstance(filt, dict):
        filt = {}
    fields = definition.get("fields") or {}
    date_field = str(fields.get("date") or "date")
    amount_field = str(fields.get("amount") or "cost")
    quantity_field = str(fields.get("quantity") or "liters")
    label_field = str(fields.get("label") or "station")

    try:
        files = iter_markdown_files(kb_root, relative)
    except VaultReadError:
        logger.warning("board path escapes KB root: %s", relative)
        return []

    entries: list[AggEntry] = []
    root = kb_root.resolve()
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                post = frontmatter.load(handle)
        except OSError as exc:
            logger.warning("skip unreadable note %s: %s", path, exc)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("skip unparseable note %s: %s", path, exc)
            continue

        meta = post.metadata or {}
        if filt and not _filter_matches(meta, filt):
            continue
        note_date = _parse_date(_meta_get(meta, date_field))
        amount = _parse_float(_meta_get(meta, amount_field))
        if note_date is None or amount is None:
            continue
        quantity = _parse_float(_meta_get(meta, quantity_field))
        try:
            rel = str(path.resolve().relative_to(root))
        except ValueError:
            rel = path.name
        entries.append(
            AggEntry(
                date=note_date,
                amount=amount,
                quantity=quantity,
                label=_clean_wikilink(_meta_get(meta, label_field)),
                path=rel,
            )
        )

    entries.sort(key=lambda e: (e.date, e.path), reverse=True)
    return entries


def load_sidecar(kb_root: Path, sidecar: dict[str, Any]) -> dict[str, Any] | None:
    """Load one note (e.g. active trainer_block) for a progress callout. Read-only."""
    relative = str(sidecar.get("path") or "").strip()
    if not relative:
        return None
    filt = sidecar.get("filter") or {}
    if not isinstance(filt, dict):
        filt = {}
    fields = sidecar.get("fields") or {}
    date_field = str(fields.get("date") or "started")
    done_field = str(fields.get("done") or "done")
    remaining_field = str(fields.get("remaining") or "remaining")
    total_field = str(fields.get("total") or "total")
    label_field = str(fields.get("label") or "title")

    try:
        files = iter_markdown_files(kb_root, relative)
    except VaultReadError:
        return None

    root = kb_root.resolve()
    best: dict[str, Any] | None = None
    best_date: date | None = None
    for path in files:
        try:
            with path.open("r", encoding="utf-8") as handle:
                post = frontmatter.load(handle)
        except Exception:  # noqa: BLE001
            continue
        meta = post.metadata or {}
        if filt and not _filter_matches(meta, filt):
            continue
        note_date = _parse_date(_meta_get(meta, date_field))
        done = _parse_float(_meta_get(meta, done_field))
        total = _parse_float(_meta_get(meta, total_field))
        if done is None or total is None:
            continue
        remaining = _parse_float(_meta_get(meta, remaining_field))
        if remaining is None:
            remaining = max(total - done, 0.0)
        try:
            rel = str(path.resolve().relative_to(root))
        except ValueError:
            rel = path.name
        candidate = {
            "date": note_date,
            "done": int(round(done)),
            "remaining": int(round(remaining)),
            "total": int(round(total)),
            "label": _clean_wikilink(_meta_get(meta, label_field)) or "Блок",
            "path": rel,
        }
        if best is None or (note_date and (best_date is None or note_date >= best_date)):
            best = candidate
            best_date = note_date
    return best


def _month_total(entries: list[AggEntry], today: date) -> float:
    return sum(e.amount for e in entries if e.date.year == today.year and e.date.month == today.month)


def build_document(
    entries: list[AggEntry],
    definition: dict[str, Any],
    *,
    today: date | None = None,
    sidecar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    recent_limit = int(definition.get("recent_limit") or 10)
    labels = definition.get("labels") or {}
    title = str(labels.get("title") or "Сводка")
    readonly = str(
        labels.get("readonly")
        or "Сводка только читает заметки из vault. Файлы не изменяются."
    )
    metric_month = str(labels.get("metric_month") or "Этот месяц")
    metric_total = str(labels.get("metric_total") or "Всего")
    metric_last = str(labels.get("metric_last") or "Последняя")
    metric_count = str(labels.get("metric_count") or "Записей")
    table_label = str(labels.get("table") or "Последние записи")
    col_date = str(labels.get("col_date") or "Дата")
    col_label = str(labels.get("col_label") or "Название")
    col_qty = str(labels.get("col_qty") or "Кол-во")
    col_amount = str(labels.get("col_amount") or "Сумма")
    currency = str(labels.get("currency") or "₽")

    total = sum(e.amount for e in entries)
    month = _month_total(entries, today)
    last = entries[0] if entries else None
    recent = entries[:recent_limit]

    metrics_children = [
        {"type": "metric", "id": "m_month", "label": metric_month, "text": f"{_format_money(month)} {currency}"},
        {"type": "metric", "id": "m_total", "label": metric_total, "text": f"{_format_money(total)} {currency}"},
        {
            "type": "metric",
            "id": "m_last",
            "label": metric_last,
            "text": f"{_format_money(last.amount)} {currency}" if last else "—",
        },
        {"type": "metric", "id": "m_count", "label": metric_count, "text": str(len(entries))},
    ]

    rows = [
        [
            e.date.isoformat(),
            e.label or "—",
            _format_qty(e.quantity),
            f"{_format_money(e.amount)} {currency}",
        ]
        for e in recent
    ]

    children: list[dict[str, Any]] = [
        {"type": "text", "id": "title", "text": title},
        {"type": "callout", "id": "readonly", "text": readonly, "variant": "info"},
        {"type": "hstack", "id": "metrics_row", "spacing": 12, "children": metrics_children},
    ]
    if sidecar:
        block_name = str(sidecar.get("label") or "Блок")
        done = sidecar.get("done")
        total_n = sidecar.get("total")
        remaining = sidecar.get("remaining")
        tip = f"{block_name}: {done} / {total_n}, осталось {remaining}"
        children.append({"type": "callout", "id": "block_progress", "text": tip, "variant": "tip"})
    if last:
        tip = f"{metric_last}: {last.date.isoformat()}"
        if last.label:
            tip += f", {last.label}"
        if last.quantity is not None:
            tip += f", {_format_qty(last.quantity)}"
        children.append({"type": "callout", "id": "last_detail", "text": tip, "variant": "tip"})

    children.append(
        {
            "type": "table",
            "id": "recent_rows",
            "label": f"{table_label} ({len(recent)})",
            "scroll_horizontal": False,
            "columns": [
                {"id": "date", "label": col_date},
                {"id": "label", "label": col_label},
                {"id": "qty", "label": col_qty},
                {"id": "amount", "label": col_amount},
            ],
            "rows": rows,
        }
    )
    return {"schema_version": 1, "screen": {"type": "vstack", "id": "root", "children": children}}


def build_list_cell(
    entries: list[AggEntry],
    definition: dict[str, Any],
    *,
    today: date | None = None,
    sidecar: dict[str, Any] | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    labels = definition.get("labels") or {}
    currency = str(labels.get("currency") or "₽")
    month = _month_total(entries, today)
    last = entries[0] if entries else None
    metrics = [
        {"label": str(labels.get("metric_month") or "Месяц"), "value": f"{_format_money(month)} {currency}"},
        {
            "label": str(labels.get("metric_last") or "Последняя"),
            "value": f"{_format_money(last.amount)} {currency}" if last else "—",
        },
    ]
    if sidecar and sidecar.get("total") is not None:
        metrics.append(
            {
                "label": str(labels.get("metric_block") or "Блок"),
                "value": f"{sidecar.get('done')}/{sidecar.get('total')}",
            }
        )
    return {
        "kind": "metrics",
        "title": str(labels.get("list_title") or labels.get("title") or "Сводка"),
        "subtitle": str(labels.get("list_subtitle") or ""),
        "metrics": metrics,
    }


def compute(kb_root: Path, board_meta: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    """Render board list_cell + document from definition. Read-only."""
    path = str(definition.get("path") or "").strip()
    if path:
        try:
            resolve_under_root(kb_root, path)
        except VaultReadError as exc:
            logger.error("invalid board path: %s", exc)
            entries: list[AggEntry] = []
        else:
            entries = load_entries(kb_root, definition)
    else:
        entries = []

    sidecar_meta: dict[str, Any] | None = None
    sidecar_def = definition.get("sidecar")
    if isinstance(sidecar_def, dict) and sidecar_def.get("path"):
        try:
            resolve_under_root(kb_root, str(sidecar_def["path"]))
        except VaultReadError as exc:
            logger.error("invalid sidecar path: %s", exc)
        else:
            sidecar_meta = load_sidecar(kb_root, sidecar_def)

    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    list_cell = build_list_cell(entries, definition, sidecar=sidecar_meta)
    board = {
        "id": board_meta["id"],
        "title": board_meta.get("title") or list_cell.get("title") or board_meta["id"],
        "subtitle": board_meta.get("subtitle") or list_cell.get("subtitle"),
        "icon": board_meta.get("icon"),
        "kind": board_meta.get("kind") or "cached_view",
        "sort_order": int(board_meta.get("sort_order") or 0),
        "enabled": bool(board_meta.get("enabled", True)),
        "list_cell": list_cell,
        "rendered_at": rendered_at,
    }
    return {
        "board": board,
        "document": build_document(entries, definition, sidecar=sidecar_meta),
        "rendered_at": rendered_at,
    }
