"""Локальные тесты без pytest: python -m unittest tests.test_linking"""
import json
import tempfile
import unittest
from pathlib import Path

from health_linking import find_workout_note, process_sync_payload


class TestFindWorkoutNote(unittest.TestCase):
    def test_finds_note_by_date_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            note_dir = kb / "Тренировки" / "2026" / "Июнь"
            note_dir.mkdir(parents=True)
            note = note_dir / "2026-06-15 Понедельник — Грудь.md"
            note.write_text("---\ntitle: x\n---\nbody\n", encoding="utf-8")
            found = find_workout_note(kb, "2026-06-15")
            self.assertEqual(found, note)


class TestProcessSync(unittest.TestCase):
    def test_links_workout_when_note_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            note_dir = kb / "Тренировки" / "2026" / "Июнь"
            note_dir.mkdir(parents=True)
            note_path = note_dir / "2026-06-15 Понедельник — Тест.md"
            note_path.write_text("---\n---\n", encoding="utf-8")

            daily_dir = kb / "HealthData" / "daily"
            daily_dir.mkdir(parents=True)
            (daily_dir / "2026-06-15.json").write_text(
                json.dumps({"sleep": {"total_minutes": 420}}),
                encoding="utf-8",
            )

            wo_dir = kb / "HealthData" / "workouts"
            wo_dir.mkdir(parents=True)
            rel = "HealthData/workouts/2026-06-15_abc.json"
            wpath = kb / rel
            wpath.write_text(
                json.dumps(
                    {
                        "date": "2026-06-15",
                        "workout_type": "traditional_strength_training",
                        "avg_heart_rate": 120,
                        "max_heart_rate": 150,
                        "active_calories": 300,
                        "duration_minutes": 60,
                    }
                ),
                encoding="utf-8",
            )

            result = process_sync_payload(kb, "2026-06-15", [rel])
            self.assertEqual(len(result.linked), 1)
            self.assertEqual(len(result.errors), 0)
            data = json.loads(wpath.read_text(encoding="utf-8"))
            self.assertTrue(data["linked_note"].endswith(".md"))
            self.assertIn("Тренировки", data["linked_note"])

    def test_skips_non_strength_workout(self):
        with tempfile.TemporaryDirectory() as tmp:
            kb = Path(tmp)
            note_dir = kb / "Тренировки" / "2026" / "Июнь"
            note_dir.mkdir(parents=True)
            (note_dir / "2026-06-15 Понедельник — Тест.md").write_text("---\n---\n", encoding="utf-8")

            wo_dir = kb / "HealthData" / "workouts"
            wo_dir.mkdir(parents=True)
            rel = "HealthData/workouts/2026-06-15_run.json"
            (kb / rel).write_text(
                json.dumps({"date": "2026-06-15", "workout_type": "running"}),
                encoding="utf-8",
            )

            result = process_sync_payload(kb, "2026-06-15", [rel])
            self.assertEqual(len(result.linked), 0)
            self.assertTrue(any("unsupported_type" in s for s in result.skipped))


if __name__ == "__main__":
    unittest.main()
