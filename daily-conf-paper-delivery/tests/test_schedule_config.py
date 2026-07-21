import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "schedule_config.py"
SPEC = importlib.util.spec_from_file_location("schedule_config", MODULE_PATH)
schedule_config = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(schedule_config)


class ScheduleConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "user-config.local.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_updates_time_without_losing_preferences(self):
        self.config_path.write_text(
            json.dumps(
                {
                    "daily_papers": {"topics": ["Recommendation Systems"]},
                    "automation": {"git_commit": False, "daily_run_time": "08:00"},
                }
            ),
            encoding="utf-8",
        )

        changed = schedule_config.set_daily_run_time(self.config_path, "09:30")
        updated = json.loads(self.config_path.read_text(encoding="utf-8"))

        self.assertTrue(changed)
        self.assertEqual(updated["daily_papers"]["topics"], ["Recommendation Systems"])
        self.assertFalse(updated["automation"]["git_commit"])
        self.assertEqual(updated["automation"]["daily_run_time"], "09:30")

    def test_rejects_invalid_time(self):
        self.config_path.write_text("{}", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "24-hour HH:MM"):
            schedule_config.set_daily_run_time(self.config_path, "25:00")

    def test_requires_an_existing_local_config(self):
        with self.assertRaisesRegex(FileNotFoundError, "Daily config not found"):
            schedule_config.set_daily_run_time(self.config_path, "08:00")


if __name__ == "__main__":
    unittest.main()
