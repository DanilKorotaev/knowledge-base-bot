"""Tests for vault_json_daily_agg provider."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kb_app_api.boards.providers import vault_json_daily_agg as agg


class VaultJsonDailyAggTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        daily = self.root / "HealthData" / "daily"
        workouts = self.root / "HealthData" / "workouts"
        daily.mkdir(parents=True)
        workouts.mkdir(parents=True)
        (daily / "2026-08-01.json").write_text(
            json.dumps(
                {
                    "date": "2026-08-01",
                    "steps": 1000,
                    "distance_km": 1.5,
                    "active_calories": 400,
                    "exercise_minutes": 30,
                    "sleep": {"total_minutes": 420},
                }
            ),
            encoding="utf-8",
        )
        (daily / "2026-09-01.json").write_text(
            json.dumps(
                {
                    "date": "2026-09-01",
                    "steps": 2000,
                    "distance_km": 2.5,
                    "active_calories": 500,
                    "exercise_minutes": 40,
                    "sleep": {"total_minutes": 480},
                }
            ),
            encoding="utf-8",
        )
        (workouts / "2026-09-01_a.json").write_text(
            json.dumps({"date": "2026-09-01", "workout_type": "run"}),
            encoding="utf-8",
        )
        (workouts / "2026-08-01_b.json").write_text(
            json.dumps({"date": "2026-08-01", "workout_type": "walk"}),
            encoding="utf-8",
        )

    def test_period_and_metrics(self) -> None:
        definition = {
            "provider": "vault_json_daily_agg",
            "path": "HealthData/daily",
            "date_field": "date",
            "period_ui": "range",
            "show_table": False,
            "sources": [{"id": "workouts", "path": "HealthData/workouts", "date_field": "date"}],
            "metrics": [
                {"id": "steps", "field": "steps", "agg": "sum", "label": "Steps"},
                {
                    "id": "sleep",
                    "field": "sleep.total_minutes",
                    "agg": "avg",
                    "label": "Sleep",
                    "unit": "h",
                    "scale": 1 / 60,
                    "decimals": 1,
                },
                {"id": "workouts", "source": "workouts", "agg": "count", "label": "Workouts"},
            ],
            "labels": {"title": "Health"},
        }
        meta = {"id": "health", "title": "Health", "kind": "cached_view", "sort_order": 1}
        sep = agg.compute(self.root, meta, definition, period="2026-09")
        self.assertEqual(sep["board"]["period_ui"], "range")
        metrics = next(n for n in sep["document"]["screen"]["children"] if n.get("id") == "metrics_row")
        by_id = {c["id"]: c["text"] for c in metrics["children"]}
        self.assertEqual(by_id["steps"], "2 000")
        self.assertIn("8", by_id["sleep"])  # 480/60
        self.assertEqual(by_id["workouts"], "1")
        self.assertFalse(any(n.get("type") == "table" for n in sep["document"]["screen"]["children"]))


if __name__ == "__main__":
    unittest.main()
