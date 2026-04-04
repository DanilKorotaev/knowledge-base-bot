"""python -m unittest discover -s packages/health_linking/tests -p 'test*.py' (PYTHONPATH=packages/health_linking)"""
import tempfile
import unittest
from pathlib import Path

from health_linking import workout_json_rel_paths_for_date


class TestWorkoutJsonPaths(unittest.TestCase):
    def test_collects_by_date_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            wo = kb / "HealthData" / "workouts"
            wo.mkdir(parents=True)
            (wo / "2026-06-15_aaa.json").write_text("{}", encoding="utf-8")
            (wo / "2026-06-14_other.json").write_text("{}", encoding="utf-8")
            paths = workout_json_rel_paths_for_date(kb, "2026-06-15")
            self.assertEqual(paths, ["HealthData/workouts/2026-06-15_aaa.json"])


if __name__ == "__main__":
    unittest.main()
