from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActivityGoals:
    active_calories: float = 500.0
    exercise_minutes: float = 30.0
    stand_hours: float = 12.0


DEFAULT_GOALS = ActivityGoals()


@dataclass(frozen=True)
class AggregatePaths:
    daily_subdir: str = "HealthData/daily"
    derived_subdir: str = "HealthData/derived"


DEFAULT_PATHS = AggregatePaths()


def _load_daily_files(kb: Path, paths: AggregatePaths) -> dict[str, dict[str, Any]]:
    daily_dir = kb / paths.daily_subdir
    if not daily_dir.is_dir():
        return {}
    out: dict[str, dict[str, Any]] = {}
    for p in daily_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Skip daily %s: %s", p.name, e)
            continue
        d = data.get("date") or p.stem
        if isinstance(d, str):
            out[d] = data
    return out


def _sleep_hours(data: dict[str, Any]) -> float | None:
    sleep = data.get("sleep")
    if not isinstance(sleep, dict):
        return None
    total = sleep.get("total_minutes")
    if isinstance(total, (int, float)) and total > 0:
        return float(total) / 60.0
    return None


def _num(data: dict[str, Any], key: str) -> float | None:
    val = data.get(key)
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _months_back_start(reference: date, months: int) -> date:
    """Первый день календарного месяца N месяцев назад (включая текущий)."""
    y, m = reference.year, reference.month
    m -= months - 1
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def _period_stats(days: list[dict[str, Any]]) -> dict[str, Any]:
    if not days:
        return {"days_with_data": 0}

    def avg(key: str) -> float | None:
        vals = [_num(d, key) for d in days]
        nums = [v for v in vals if v is not None]
        if not nums:
            return None
        return round(sum(nums) / len(nums), 2)

    def avg_sleep() -> float | None:
        vals = [_sleep_hours(d) for d in days]
        nums = [v for v in vals if v is not None]
        if not nums:
            return None
        return round(sum(nums) / len(nums), 2)

    def total(key: str) -> float | None:
        vals = [_num(d, key) for d in days]
        nums = [v for v in vals if v is not None]
        if not nums:
            return None
        return round(sum(nums), 2)

    return {
        "days_with_data": len(days),
        "avg_sleep_hours": avg_sleep(),
        "avg_active_calories": avg("active_calories"),
        "avg_total_calories": avg("total_calories"),
        "avg_exercise_minutes": avg("exercise_minutes"),
        "avg_stand_hours": avg("stand_hours"),
        "avg_steps": avg("steps"),
        "avg_distance_km": avg("distance_km"),
        "avg_resting_heart_rate": avg("resting_heart_rate"),
        "avg_hrv": avg("hrv_avg"),
        "total_active_calories": total("active_calories"),
        "total_steps": total("steps"),
    }


def _day_ring_metrics(
    data: dict[str, Any],
    default_goals: ActivityGoals,
) -> tuple[dict[str, float | None], dict[str, float | None]]:
    rings = data.get("activity_rings")
    if isinstance(rings, dict):
        actual = {
            "move": _num(rings, "active_calories"),
            "exercise": _num(rings, "exercise_minutes"),
            "stand": _num(rings, "stand_hours"),
        }
        goals = {
            "move": _num(rings, "active_calories_goal") or default_goals.active_calories,
            "exercise": _num(rings, "exercise_minutes_goal") or default_goals.exercise_minutes,
            "stand": _num(rings, "stand_hours_goal") or default_goals.stand_hours,
        }
        return actual, goals

    return (
        {
            "move": _num(data, "active_calories"),
            "exercise": _num(data, "exercise_minutes"),
            "stand": _num(data, "stand_hours"),
        },
        {
            "move": default_goals.active_calories,
            "exercise": default_goals.exercise_minutes,
            "stand": default_goals.stand_hours,
        },
    )


def _ring_closed(data: dict[str, Any], default_goals: ActivityGoals) -> dict[str, bool]:
    actual, goals = _day_ring_metrics(data, default_goals)

    def closed(key: str) -> bool:
        value = actual[key]
        goal = goals[key]
        return value is not None and goal is not None and value >= goal

    move = closed("move")
    exercise = closed("exercise")
    stand = closed("stand")
    return {
        "move": move,
        "exercise": exercise,
        "stand": stand,
        "all": move and exercise and stand,
    }


def _compute_streaks(
    sorted_dates: list[str],
    daily: dict[str, dict[str, Any]],
    default_goals: ActivityGoals,
) -> dict[str, Any]:
    if not sorted_dates:
        return {
            "current_all_rings": 0,
            "longest_all_rings": 0,
            "current_move": 0,
            "longest_move": 0,
            "current_exercise": 0,
            "longest_exercise": 0,
            "current_stand": 0,
            "longest_stand": 0,
        }

    def streak_for(key: str) -> tuple[int, int]:
        longest = 0
        run = 0
        for d in sorted_dates:
            rings = _ring_closed(daily[d], default_goals)
            if rings[key]:
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        current = 0
        for d in reversed(sorted_dates):
            rings = _ring_closed(daily[d], default_goals)
            if rings[key]:
                current += 1
            else:
                break
        return current, longest

    ca, la = streak_for("all")
    cm, lm = streak_for("move")
    ce, le = streak_for("exercise")
    cs, ls = streak_for("stand")
    return {
        "current_all_rings": ca,
        "longest_all_rings": la,
        "current_move": cm,
        "longest_move": lm,
        "current_exercise": ce,
        "longest_exercise": le,
        "current_stand": cs,
        "longest_stand": ls,
    }


def _monthly_aggregates(daily: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    by_month: dict[str, list[dict[str, Any]]] = {}
    for d_str, data in daily.items():
        month_key = d_str[:7]
        by_month.setdefault(month_key, []).append(data)
    out: list[dict[str, Any]] = []
    for month in sorted(by_month):
        stats = _period_stats(by_month[month])
        stats["month"] = month
        out.append(stats)
    return out


def _series_for_days(
    sorted_dates: list[str],
    daily: dict[str, dict[str, Any]],
    value_fn,
) -> dict[str, list[Any]]:
    labels: list[str] = []
    values: list[float | None] = []
    for d in sorted_dates:
        labels.append(d)
        val = value_fn(daily[d])
        values.append(round(val, 2) if isinstance(val, float) else val)
    return {"labels": labels, "values": values}


def refresh_derived(
    kb: Path,
    paths: AggregatePaths = DEFAULT_PATHS,
    goals: ActivityGoals = DEFAULT_GOALS,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """
    Пересчитать `HealthData/derived/*.json` из daily JSON.
    Возвращает summary dict (тот же, что пишется в summary.json).
    """
    ref = reference_date or date.today()
    daily = _load_daily_files(kb, paths)
    sorted_dates = sorted(daily.keys())

    def days_in_range(start: date, end: date) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        cur = start
        while cur <= end:
            key = cur.isoformat()
            if key in daily:
                out.append(daily[key])
            cur += timedelta(days=1)
        return out

    current_month_start = _month_start(ref)
    periods = {
        "current_month": {
            "label": ref.strftime("%Y-%m"),
            "from": current_month_start.isoformat(),
            "to": ref.isoformat(),
            **_period_stats(days_in_range(current_month_start, ref)),
        },
        "last_3_calendar_months": {
            "from": _months_back_start(ref, 3).isoformat(),
            "to": ref.isoformat(),
            **_period_stats(days_in_range(_months_back_start(ref, 3), ref)),
        },
        "last_6_calendar_months": {
            "from": _months_back_start(ref, 6).isoformat(),
            "to": ref.isoformat(),
            **_period_stats(days_in_range(_months_back_start(ref, 6), ref)),
        },
        "last_12_calendar_months": {
            "from": _months_back_start(ref, 12).isoformat(),
            "to": ref.isoformat(),
            **_period_stats(days_in_range(_months_back_start(ref, 12), ref)),
        },
        "all_time": {
            "from": sorted_dates[0] if sorted_dates else None,
            "to": sorted_dates[-1] if sorted_dates else None,
            **_period_stats([daily[d] for d in sorted_dates]),
        },
    }

    rings = _compute_streaks(sorted_dates, daily, goals)
    ring_days = sum(
        1 for d in sorted_dates if _ring_closed(daily[d], goals)["all"]
    )
    days_with_activity_rings = sum(
        1
        for d in sorted_dates
        if isinstance(daily[d].get("activity_rings"), dict)
    )

    ref_key = ref.isoformat()
    current_goals = goals
    if ref_key in daily:
        _actual, ref_goals = _day_ring_metrics(daily[ref_key], goals)
        current_goals = ActivityGoals(
            active_calories=ref_goals["move"] or goals.active_calories,
            exercise_minutes=ref_goals["exercise"] or goals.exercise_minutes,
            stand_hours=ref_goals["stand"] or goals.stand_hours,
        )

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "reference_date": ref.isoformat(),
        "goals": {
            "active_calories": current_goals.active_calories,
            "exercise_minutes": current_goals.exercise_minutes,
            "stand_hours": current_goals.stand_hours,
            "source": "activity_rings" if ref_key in daily and isinstance(daily[ref_key].get("activity_rings"), dict) else "default",
        },
        "periods": periods,
        "rings": {
            **rings,
            "days_all_rings_closed": ring_days,
            "days_with_activity_rings": days_with_activity_rings,
        },
        "daily_files_count": len(sorted_dates),
    }

    derived_dir = kb / paths.derived_subdir
    derived_dir.mkdir(parents=True, exist_ok=True)

    def write_json(name: str, payload: dict[str, Any]) -> None:
        path = derived_dir / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    write_json("summary.json", summary)
    write_json("monthly.json", {"months": _monthly_aggregates(daily)})

    for window, suffix in ((30, "30d"), (90, "90d"), (365, "365d")):
        start = ref - timedelta(days=window - 1)
        window_dates = [d for d in sorted_dates if start.isoformat() <= d <= ref.isoformat()]
        series_base = {"window": suffix, "from": start.isoformat(), "to": ref.isoformat()}
        write_json(
            f"series_sleep_{suffix}.json",
            {
                **series_base,
                **_series_for_days(window_dates, daily, _sleep_hours),
            },
        )
        write_json(
            f"series_active_calories_{suffix}.json",
            {
                **series_base,
                **_series_for_days(window_dates, daily, lambda d: _num(d, "active_calories")),
            },
        )
        write_json(
            f"series_steps_{suffix}.json",
            {
                **series_base,
                **_series_for_days(window_dates, daily, lambda d: _num(d, "steps")),
            },
        )
        write_json(
            f"series_exercise_minutes_{suffix}.json",
            {
                **series_base,
                **_series_for_days(window_dates, daily, lambda d: _num(d, "exercise_minutes")),
            },
        )

    # Текущий календарный месяц — по дням (для графиков без селектора)
    cm_dates = [
        d for d in sorted_dates if current_month_start.isoformat() <= d <= ref.isoformat()
    ]
    cm_base = {
        "window": "current_month",
        "from": current_month_start.isoformat(),
        "to": ref.isoformat(),
    }
    write_json(
        "series_sleep_current_month.json",
        {**cm_base, **_series_for_days(cm_dates, daily, _sleep_hours)},
    )
    write_json(
        "series_active_calories_current_month.json",
        {
            **cm_base,
            **_series_for_days(cm_dates, daily, lambda d: _num(d, "active_calories")),
        },
    )

    logger.info(
        "Health derived refreshed: %d daily files → %s",
        len(sorted_dates),
        derived_dir,
    )
    return summary
