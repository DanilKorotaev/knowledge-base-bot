"""Generic aggregator over vault JSON day files (e.g. HealthData/daily/*.json).

All paths/fields/metrics come from board ``definition`` JSON — no domain labels in code.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from kb_app_api.boards.vault_io import VaultReadError, resolve_under_root

logger = logging.getLogger(__name__)

PROVIDER_ID = "vault_json_daily_agg"


def _parse_iso_date(raw: Any) -> date | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_period(period: str | None) -> tuple[int, int] | None:
    if not period or str(period).strip().lower() in ("", "all", "*", "range"):
        return None
    text = str(period).strip()
    try:
        year_s, month_s = text.split("-", 1)
        year, month = int(year_s), int(month_s)
        if month < 1 or month > 12:
            return None
        return year, month
    except ValueError:
        return None


def _meta_get(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in str(dotted).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _as_float(raw: Any) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and (math.isnan(raw) or math.isinf(raw)):
            return None
        return float(raw)
    try:
        return float(str(raw).replace(",", ".").strip())
    except ValueError:
        return None


def _format_number(value: float, *, decimals: int | None) -> str:
    if decimals is None:
        if abs(value - round(value)) < 1e-9:
            return f"{int(round(value)):,}".replace(",", " ")
        decimals = 1
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",")


def _load_day_records(
    kb_root: Path,
    *,
    relative: str,
    date_field: str,
) -> list[tuple[date, dict[str, Any]]]:
    try:
        folder = resolve_under_root(kb_root, relative)
    except VaultReadError as exc:
        logger.error("invalid json daily path: %s", exc)
        return []
    if not folder.is_dir():
        return []
    out: list[tuple[date, dict[str, Any]]] = []
    for path in sorted(folder.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        day = _parse_iso_date(payload.get(date_field) or path.stem[:10])
        if day is None:
            continue
        out.append((day, payload))
    return out


def _filter_records(
    records: list[tuple[date, dict[str, Any]]],
    *,
    period: str | None,
    date_from: date | None,
    date_to: date | None,
) -> list[tuple[date, dict[str, Any]]]:
    if date_from is not None or date_to is not None:
        out: list[tuple[date, dict[str, Any]]] = []
        for day, payload in records:
            if date_from is not None and day < date_from:
                continue
            if date_to is not None and day > date_to:
                continue
            out.append((day, payload))
        return out
    bounds = _parse_period(period)
    if bounds is None:
        return records
    year, month = bounds
    return [(d, p) for d, p in records if d.year == year and d.month == month]


def _metric_value(
    records: list[tuple[date, dict[str, Any]]],
    metric: dict[str, Any],
) -> float | None:
    agg = str(metric.get("agg") or "sum").strip().lower()
    if agg == "count":
        return float(len(records))
    field = str(metric.get("field") or "").strip()
    if not field:
        return None
    scale = _as_float(metric.get("scale"))
    if scale is None:
        scale = 1.0
    values: list[float] = []
    for _, payload in records:
        raw = _meta_get(payload, field)
        num = _as_float(raw)
        if num is None:
            continue
        values.append(num * scale)
    if not values:
        return None
    if agg == "avg":
        return sum(values) / len(values)
    if agg == "max":
        return max(values)
    if agg == "min":
        return min(values)
    if agg == "last":
        return values[-1]
    return sum(values)


def compute(
    kb_root: Path,
    board_meta: dict[str, Any],
    definition: dict[str, Any],
    *,
    period: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    path = str(definition.get("path") or "").strip()
    date_field = str(definition.get("date_field") or "date").strip() or "date"
    labels = definition.get("labels") or {}
    metrics_def = definition.get("metrics") or []
    if not isinstance(metrics_def, list):
        metrics_def = []

    records = _load_day_records(kb_root, relative=path, date_field=date_field) if path else []
    from_d = _parse_iso_date(date_from)
    to_d = _parse_iso_date(date_to)
    records = _filter_records(records, period=period, date_from=from_d, date_to=to_d)
    scoped = from_d is not None or to_d is not None or _parse_period(period) is not None

    # Optional extra sources (e.g. workouts folder → count).
    sources = definition.get("sources")
    source_records: dict[str, list[tuple[date, dict[str, Any]]]] = {"main": records}
    if isinstance(sources, list):
        for src in sources:
            if not isinstance(src, dict):
                continue
            sid = str(src.get("id") or "").strip()
            spath = str(src.get("path") or "").strip()
            if not sid or not spath:
                continue
            sdate = str(src.get("date_field") or "date").strip() or "date"
            loaded = _load_day_records(kb_root, relative=spath, date_field=sdate)
            source_records[sid] = _filter_records(
                loaded, period=period, date_from=from_d, date_to=to_d
            )

    period_ui = str(definition.get("period_ui") or "month").strip().lower()
    if period_ui not in ("none", "month", "range"):
        period_ui = "month"

    title = str(labels.get("title") or board_meta.get("title") or board_meta["id"])
    children: list[dict[str, Any]] = [
        {"type": "text", "id": "title", "text": title},
    ]
    metric_nodes: list[dict[str, Any]] = []
    list_metrics: list[dict[str, str]] = []

    for idx, metric in enumerate(metrics_def):
        if not isinstance(metric, dict):
            continue
        mid = str(metric.get("id") or f"m{idx}")
        label = str(metric.get("label") or mid)
        src_id = str(metric.get("source") or "main").strip() or "main"
        pool = source_records.get(src_id) or []
        value = _metric_value(pool, metric)
        if value is None:
            text = "—"
        else:
            decimals = metric.get("decimals")
            decimals_i = int(decimals) if decimals is not None else None
            text = _format_number(value, decimals=decimals_i)
            unit = str(metric.get("unit") or "").strip()
            if unit:
                text = f"{text} {unit}"
        metric_nodes.append({"type": "metric", "id": mid, "label": label, "text": text})
        list_metrics.append({"label": label, "value": text})

    if metric_nodes:
        children.append(
            {"type": "hstack", "id": "metrics_row", "spacing": 12, "children": metric_nodes}
        )

    charts_def = definition.get("charts") or []
    if isinstance(charts_def, list):
        for cidx, chart in enumerate(charts_def):
            if not isinstance(chart, dict):
                continue
            cid = str(chart.get("id") or f"chart{cidx}")
            clabel = str(chart.get("label") or cid)
            src_id = str(chart.get("source") or "main").strip() or "main"
            field = str(chart.get("field") or "").strip()
            if not field:
                continue
            pool = source_records.get(src_id) or []
            scale = _as_float(chart.get("scale"))
            if scale is None:
                scale = 1.0
            series: list[dict[str, Any]] = []
            for day, payload in pool:
                num = _as_float(_meta_get(payload, field))
                if num is None:
                    continue
                series.append({"x": day.isoformat(), "y": num * scale})
            max_points = int(chart.get("max_points") or 90)
            if max_points > 0 and len(series) > max_points:
                step = max(1, len(series) // max_points)
                series = series[::step][:max_points]
            if series:
                children.append(
                    {
                        "type": "chart",
                        "id": cid,
                        "label": clabel,
                        "series": series,
                    }
                )

    tip = str(labels.get("tip") or "").strip()
    if tip:
        children.append({"type": "callout", "id": "tip", "text": tip, "variant": "tip"})

    show_table = bool(definition.get("show_table"))
    if show_table and records:
        # Keep optional; Health board uses metrics-only.
        recent_limit = int(definition.get("recent_limit") or 10)
        recent = list(reversed(records[-recent_limit:]))
        rows = [[d.isoformat(), str(_meta_get(p, "steps") or "—")] for d, p in recent]
        children.append(
            {
                "type": "table",
                "id": "recent_rows",
                "label": str(labels.get("table") or "Recent"),
                "columns": [
                    {"id": "date", "label": str(labels.get("col_date") or "Date")},
                    {"id": "steps", "label": str(labels.get("col_steps") or "Steps")},
                ],
                "rows": rows,
            }
        )

    rendered_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    list_cell = {
        "kind": "metrics",
        "title": str(labels.get("list_title") or title),
        "subtitle": str(labels.get("list_subtitle") or board_meta.get("subtitle") or ""),
        "metrics": list_metrics[:4],
    }
    board = {
        "id": board_meta["id"],
        "title": board_meta.get("title") or title,
        "subtitle": board_meta.get("subtitle") or list_cell.get("subtitle"),
        "icon": board_meta.get("icon"),
        "kind": board_meta.get("kind") or "cached_view",
        "sort_order": int(board_meta.get("sort_order") or 0),
        "enabled": bool(board_meta.get("enabled", True)),
        "list_cell": list_cell,
        "rendered_at": rendered_at,
        "period_ui": period_ui,
    }
    return {
        "board": board,
        "document": {"schema_version": 1, "screen": {"type": "vstack", "id": "root", "children": children}},
        "rendered_at": rendered_at,
        "period": period or ("range" if scoped else "all"),
        "from": from_d.isoformat() if from_d else None,
        "to": to_d.isoformat() if to_d else None,
    }
