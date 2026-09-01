from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter

logger = logging.getLogger(__name__)

# Папки месяцев в базе (как в плане: Тренировки/2026/Март/...)
_MONTHS_RU = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)


@dataclass(frozen=True)
class LinkingPaths:
    """Относительные сегменты путей внутри корня базы знаний."""

    workouts_subdir: str = "HealthData/workouts"
    daily_subdir: str = "HealthData/daily"
    training_root: str = "Тренировки"


DEFAULT_PATHS = LinkingPaths()

# HealthKit slugs eligible for linking to training notes (extend in KB scripts if needed).
LINKABLE_WORKOUT_TYPES = frozenset({"traditional_strength_training"})


def _month_folder(year: int, month: int) -> str:
    if not 1 <= month <= 12:
        raise ValueError(f"invalid month: {month}")
    return _MONTHS_RU[month - 1]


def _parse_iso_date(date_str: str) -> tuple[int, int, int] | None:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date_str.strip())
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return y, mo, d


def _training_note_dir(kb: Path, date_str: str, paths: LinkingPaths) -> Path | None:
    parsed = _parse_iso_date(date_str)
    if not parsed:
        return None
    y, month, _ = parsed
    return kb / paths.training_root / str(y) / _month_folder(y, month)


def find_workout_note(kb: Path, date_str: str, paths: LinkingPaths = DEFAULT_PATHS) -> Path | None:
    """Первая заметка `YYYY-MM-DD *.md` в каталоге тренировок за месяц."""
    tdir = _training_note_dir(kb, date_str, paths)
    if not tdir or not tdir.is_dir():
        return None
    prefix = f"{date_str} "
    for p in sorted(tdir.iterdir()):
        if p.is_file() and p.suffix.lower() == ".md" and p.name.startswith(prefix):
            return p
    return None


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Cannot read JSON %s: %s", path, e)
        return None


def _sleep_hours_from_daily(kb: Path, date_str: str, paths: LinkingPaths) -> float | None:
    daily = kb / paths.daily_subdir / f"{date_str}.json"
    data = _load_json(daily)
    if not data:
        return None
    sleep = data.get("sleep")
    if not isinstance(sleep, dict):
        return None
    total = sleep.get("total_minutes")
    if isinstance(total, (int, float)) and total > 0:
        return round(float(total) / 60.0, 2)
    return None


def _merge_health_frontmatter(note_path: Path, health: dict[str, Any]) -> None:
    with note_path.open(encoding="utf-8") as f:
        post = frontmatter.load(f)
    meta = post.metadata
    if not isinstance(meta, dict):
        meta = {}
    existing = meta.get("health")
    if isinstance(existing, dict):
        merged = {**existing, **health}
    else:
        merged = dict(health)
    meta["health"] = merged
    post.metadata = meta
    note_path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _write_workout_json(path: Path, data: dict[str, Any], linked: str) -> None:
    out = dict(data)
    out["linked_note"] = linked
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


@dataclass
class LinkResult:
    linked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def workout_json_rel_paths_for_date(
    kb: Path,
    date_str: str,
    paths: LinkingPaths = DEFAULT_PATHS,
) -> list[str]:
    """Относительные пути `HealthData/workouts/YYYY-MM-DD_*.json` для даты (все типы тренировок)."""
    wo_dir = kb / paths.workouts_subdir
    if not wo_dir.is_dir():
        return []
    prefix = f"{date_str}_"
    out: list[str] = []
    for p in wo_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".json" and p.name.startswith(prefix):
            out.append(p.relative_to(kb).as_posix())
    return sorted(out)


def process_sync_payload(
    kb: Path,
    date: str,
    files: list[str],
    paths: LinkingPaths = DEFAULT_PATHS,
) -> LinkResult:
    """
    Для каждого workout JSON из `files` с типом из `LINKABLE_WORKOUT_TYPES`: найти заметку за дату,
    дописать `health:` в frontmatter, выставить `linked_note` в JSON.
    """
    result = LinkResult()
    prefix = paths.workouts_subdir.rstrip("/") + "/"
    for rel in files:
        rel_norm = rel.replace("\\", "/").lstrip("/")
        if not rel_norm.startswith(prefix) or not rel_norm.endswith(".json"):
            continue
        wpath = kb / rel_norm
        if not wpath.is_file():
            result.skipped.append(f"missing:{rel_norm}")
            continue
        data = _load_json(wpath)
        if not data:
            result.errors.append(f"bad_json:{rel_norm}")
            continue
        if data.get("linked_note"):
            result.skipped.append(f"already_linked:{rel_norm}")
            continue
        workout_type = data.get("workout_type")
        if workout_type not in LINKABLE_WORKOUT_TYPES:
            result.skipped.append(f"unsupported_type:{rel_norm}")
            continue
        wdate = data.get("date") or date
        if not isinstance(wdate, str):
            result.errors.append(f"no_date:{rel_norm}")
            continue
        note = find_workout_note(kb, wdate, paths)
        if not note:
            result.skipped.append(f"no_note:{rel_norm}")
            continue
        sleep_h = _sleep_hours_from_daily(kb, wdate, paths)
        workout_file_posix = _relative_posix(wpath, kb)
        health: dict[str, Any] = {
            "avg_heart_rate": data.get("avg_heart_rate"),
            "max_heart_rate": data.get("max_heart_rate"),
            "active_calories": data.get("active_calories"),
            "duration_minutes": data.get("duration_minutes"),
            "workout_file": workout_file_posix,
        }
        if sleep_h is not None:
            health["sleep_hours_prev_night"] = sleep_h
        health = {k: v for k, v in health.items() if v is not None}
        try:
            _merge_health_frontmatter(note, health)
            linked_rel = _relative_posix(note, kb)
            _write_workout_json(wpath, data, linked_rel)
            result.linked.append(f"{rel_norm}→{linked_rel}")
        except OSError as e:
            logger.exception("Link failed for %s", rel_norm)
            result.errors.append(f"{rel_norm}:{e!s}")
    return result
