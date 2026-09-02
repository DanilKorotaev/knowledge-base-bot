"""python -m unittest discover -s packages/health_aggregate/tests -p 'test*.py'"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from health_aggregate import refresh_derived


class TestRefreshDerived(unittest.TestCase):
    def test_writes_summary_and_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            daily = kb / "HealthData" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-09-01.json").write_text(
                json.dumps(
                    {
                        "date": "2026-09-01",
                        "active_calories": 400,
                        "exercise_minutes": 35,
                        "stand_hours": 12,
                        "sleep": {"total_minutes": 420},
                    }
                ),
                encoding="utf-8",
            )
            (daily / "2026-09-02.json").write_text(
                json.dumps(
                    {
                        "date": "2026-09-02",
                        "active_calories": 600,
                        "exercise_minutes": 20,
                        "stand_hours": 10,
                        "sleep": {"total_minutes": 360},
                    }
                ),
                encoding="utf-8",
            )

            summary = refresh_derived(kb, reference_date=date(2026, 9, 2))
            self.assertEqual(summary["daily_files_count"], 2)
            self.assertIn("periods", summary)
            cm = summary["periods"]["current_month"]
            self.assertEqual(cm["days_with_data"], 2)
            self.assertAlmostEqual(cm["avg_sleep_hours"], 6.5)

            derived = kb / "HealthData" / "derived"
            self.assertTrue((derived / "summary.json").is_file())
            self.assertTrue((derived / "monthly.json").is_file())
            self.assertTrue((derived / "series_sleep_90d.json").is_file())

    def test_ring_streak_uses_per_day_goals(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            daily = kb / "HealthData" / "daily"
            daily.mkdir(parents=True)
            (daily / "2026-09-01.json").write_text(
                json.dumps(
                    {
                        "date": "2026-09-01",
                        "activity_rings": {
                            "active_calories": 560,
                            "active_calories_goal": 550,
                            "exercise_minutes": 35,
                            "exercise_minutes_goal": 30,
                            "stand_hours": 10,
                            "stand_hours_goal": 10,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (daily / "2026-09-02.json").write_text(
                json.dumps(
                    {
                        "date": "2026-09-02",
                        "activity_rings": {
                            "active_calories": 700,
                            "active_calories_goal": 750,
                            "exercise_minutes": 55,
                            "exercise_minutes_goal": 60,
                            "stand_hours": 12,
                            "stand_hours_goal": 12,
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = refresh_derived(kb, reference_date=date(2026, 9, 2))
            self.assertEqual(summary["rings"]["days_all_rings_closed"], 1)
            self.assertEqual(summary["rings"]["current_all_rings"], 0)
            self.assertEqual(summary["rings"]["longest_all_rings"], 1)


    def test_streak_requires_calendar_contiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            daily = kb / "HealthData" / "daily"
            daily.mkdir(parents=True)
            rings_closed = {
                "active_calories": 800,
                "active_calories_goal": 750,
                "exercise_minutes": 70,
                "exercise_minutes_goal": 60,
                "stand_hours": 12,
                "stand_hours_goal": 10,
            }
            (daily / "2026-09-01.json").write_text(
                json.dumps({"date": "2026-09-01", "activity_rings": rings_closed}),
                encoding="utf-8",
            )
            # Gap on 2026-09-02 — no file
            (daily / "2026-09-03.json").write_text(
                json.dumps({"date": "2026-09-03", "activity_rings": rings_closed}),
                encoding="utf-8",
            )
            summary = refresh_derived(kb, reference_date=date(2026, 9, 3))
            self.assertEqual(summary["rings"]["longest_all_rings"], 1)
            self.assertEqual(summary["rings"]["current_all_rings"], 1)


if __name__ == "__main__":
    unittest.main()
