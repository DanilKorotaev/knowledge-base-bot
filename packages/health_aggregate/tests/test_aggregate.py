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


if __name__ == "__main__":
    unittest.main()
