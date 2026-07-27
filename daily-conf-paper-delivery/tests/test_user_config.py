import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "skills" / "_shared" / "user_config.py"
SPEC = importlib.util.spec_from_file_location("daily_user_config", MODULE_PATH)
user_config = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(user_config)


class DailyRunTimeTest(unittest.TestCase):
    def setUp(self):
        self.automation = user_config.load_user_config()["automation"]
        self.original = self.automation.get("daily_run_time")

    def tearDown(self):
        if self.original is None:
            self.automation.pop("daily_run_time", None)
        else:
            self.automation["daily_run_time"] = self.original

    def test_accepts_24_hour_time(self):
        self.automation["daily_run_time"] = "06:30"
        self.assertEqual(user_config.daily_run_time(), "06:30")

    def test_rejects_invalid_time(self):
        self.automation["daily_run_time"] = "25:00"
        with self.assertRaisesRegex(ValueError, "24-hour HH:MM"):
            user_config.daily_run_time()


class ScopedAutomationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        config_dir = Path(self.temp_dir.name)
        self.global_config = config_dir / "global.json"
        self.delivery_config = config_dir / "delivery.json"
        self.noter_config = config_dir / "noter.json"
        self.project_config = user_config._project_config
        self.paths_patch = mock.patch.multiple(
            self.project_config,
            GLOBAL_CONFIG_PATH=self.global_config,
            DELIVERY_CONFIG_PATH=self.delivery_config,
            NOTER_CONFIG_PATH=self.noter_config,
        )
        self.paths_patch.start()

    def tearDown(self):
        self.project_config.load_user_config.cache_clear()
        self.paths_patch.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def _write(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_automation_is_scoped_and_ignored_in_global_config(self):
        self._write(
            self.global_config,
            {
                "paths": {"markdown_root": "/tmp/notes"},
                "automation": {"git_commit": True, "git_push": True},
            },
        )
        self._write(
            self.delivery_config,
            {"automation": {"git_commit": False, "daily_run_time": "07:15"}},
        )
        self._write(
            self.noter_config,
            {"automation": {"git_commit": True, "git_push": True}},
        )
        self.project_config.load_user_config.cache_clear()

        delivery = self.project_config.load_user_config("delivery")["automation"]
        noter = self.project_config.load_user_config("noter")["automation"]

        self.assertFalse(delivery["git_commit"])
        self.assertFalse(delivery["git_push"])
        self.assertEqual(delivery["daily_run_time"], "07:15")
        self.assertTrue(noter["git_commit"])
        self.assertTrue(noter["git_push"])


class MarkdownLayoutTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.markdown_root = Path(self.temp_dir.name) / "notes"
        self.env = mock.patch.dict(
            os.environ,
            {
                "RESEARCH_PAPER_CLAW_MARKDOWN_ROOT": str(self.markdown_root),
                "DOMAIN_PAPERS_VAULT": "",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp_dir.cleanup()

    def test_daily_layout_is_created_on_demand(self):
        user_config.ensure_daily_layout()

        self.assertTrue((self.markdown_root / "DailyPapers" / "mocs").is_dir())
        self.assertTrue((self.markdown_root / "DailyPapers" / "papers").is_dir())
        self.assertFalse((self.markdown_root / "PersonalizedPaper").exists())
        self.assertFalse((self.markdown_root / "DomainPapers").exists())

    def test_manual_layout_is_created_on_demand(self):
        user_config.ensure_manual_layout()

        self.assertTrue((self.markdown_root / "PersonalizedPaper" / "mocs").is_dir())
        self.assertTrue((self.markdown_root / "PersonalizedPaper" / "papers").is_dir())
        self.assertFalse((self.markdown_root / "DailyPapers").exists())
        self.assertFalse((self.markdown_root / "DomainPapers").exists())

    def test_domain_layout_is_created_on_demand(self):
        user_config.ensure_domain_layout("Recommendation Systems")

        domain_root = self.markdown_root / "DomainPapers" / "Recommendation Systems"
        self.assertTrue((domain_root / "paper").is_dir())
        self.assertTrue((domain_root / "content").is_dir())
        self.assertFalse((self.markdown_root / "DailyPapers").exists())
        self.assertFalse((self.markdown_root / "PersonalizedPaper").exists())

    def test_domain_layout_uses_configured_folder_names(self):
        project_config = user_config._project_config
        configured_paths = {
            **project_config.DEFAULT_CONFIG["paths"],
            "domain_paper_folder": "notes",
            "domain_content_folder": "galleries",
        }
        with mock.patch.object(project_config, "paths_config", return_value=configured_paths):
            user_config.ensure_domain_layout("Recommendation Systems")

        domain_root = self.markdown_root / "DomainPapers" / "Recommendation Systems"
        self.assertTrue((domain_root / "notes").is_dir())
        self.assertTrue((domain_root / "galleries").is_dir())
        self.assertFalse((domain_root / "paper").exists())
        self.assertFalse((domain_root / "content").exists())

    def test_domain_layout_rejects_paths_outside_domain_vault(self):
        for domain in ("", ".", "..", "../escape", "nested/domain", "/absolute", " trailing"):
            with self.subTest(domain=domain):
                with self.assertRaisesRegex(ValueError, "single folder name"):
                    user_config.ensure_domain_layout(domain)

        self.assertFalse((self.markdown_root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
