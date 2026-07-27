from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
UPDATE_SCRIPT = SKILL_DIR / "scripts" / "update_domain_content.py"
ADD_WRAPPER = SKILL_DIR.parents[1] / "bin" / "domain-paper-add.sh"


class UpdateDomainContentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name) / "DomainPapers"
        self.domain = "Test Recommendation"
        self.domain_dir = self.vault / self.domain
        self.content_dir = self.domain_dir / "content"
        self.papers_dir = self.domain_dir / "paper"
        self.content_dir.mkdir(parents=True)
        self.papers_dir.mkdir(parents=True)
        self.env = {**os.environ, "DOMAIN_PAPERS_VAULT": str(self.vault)}

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_update(
        self,
        *,
        domain: str | None = None,
        category: str = "Parent / Child",
        title: str = "Test Paper",
        note: str = "TestNote",
        year: int = 2026,
        summary: str = "Test summary.",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(UPDATE_SCRIPT),
                "--domain",
                domain or self.domain,
                "--category-path",
                category,
                "--title",
                title,
                "--note",
                note,
                "--year",
                str(year),
                "--venue",
                "TestConf",
                "--summary",
                summary,
                "--abstract-en",
                f"English abstract for {title}.",
                "--abstract-zh",
                f"{title} 的中文摘要。",
                "--background",
                f"Background for {title}.",
                "--method",
                f"Method for {title}.",
                "--evaluation",
                f"Evaluation for {title}.",
                "--significance",
                f"Significance for {title}.",
            ],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_nested_gallery_is_sorted_deduplicated_and_preserves_handwritten_content(self) -> None:
        content_path = self.content_dir / "Parent" / "Child.md"
        content_path.parent.mkdir(parents=True)
        content_path.write_text(
            "# Child\n\nKeep this handwritten introduction.\n",
            encoding="utf-8",
        )

        older = self.run_update(
            title="Older Paper", note="Older", year=2025, summary="Original older summary."
        )
        newer = self.run_update(
            title="Newer Paper", note="Newer", year=2026, summary="Newer summary."
        )
        refreshed = self.run_update(
            title="Older Paper", note="Older", year=2025, summary="Updated older summary."
        )

        for result in (older, newer, refreshed):
            self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(refreshed.stdout)
        self.assertEqual(summary["entry_count"], 2)

        rendered = content_path.read_text(encoding="utf-8")
        self.assertIn("Keep this handwritten introduction.", rendered)
        self.assertEqual(rendered.count("#### "), 2)
        self.assertLess(rendered.index("Newer Paper"), rendered.index("Older Paper"))
        self.assertIn("Updated older summary.", rendered)
        self.assertNotIn("Original older summary.", rendered)

        sidecar = json.loads(
            (self.content_dir / ".domain-papers.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(sidecar["pages"]["Parent/Child.md"]), 2)
        self.assertTrue((self.content_dir / "_index.md").is_file())

    def test_rejects_invalid_domain_and_category_paths(self) -> None:
        invalid_domain = self.run_update(domain="../escaped-domain")
        self.assertNotEqual(invalid_domain.returncode, 0)
        self.assertIn("single folder name", invalid_domain.stderr)
        self.assertFalse((Path(self.temp_dir.name) / "escaped-domain").exists())

        invalid_category = self.run_update(category="Parent / ..")
        self.assertNotEqual(invalid_category.returncode, 0)
        self.assertIn("invalid category path part", invalid_category.stderr)

        invalid_wrapper_category = subprocess.run(
            [str(ADD_WRAPPER), self.domain, "Parent / ..", "Test Paper"],
            env={**self.env, "CODEX_BIN": "/usr/bin/true"},
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(invalid_wrapper_category.returncode, 0)
        self.assertIn("invalid category path part", invalid_wrapper_category.stderr)

    def test_add_wrapper_honors_custom_folder_names_and_normalizes_category(self) -> None:
        source_repo = SKILL_DIR.parents[2]
        isolated_repo = Path(self.temp_dir.name) / "repo"
        isolated_noter = isolated_repo / "research-paper-noter"
        (isolated_repo / "config").mkdir(parents=True)
        (isolated_noter / "bin").mkdir(parents=True)
        (isolated_noter / "skills" / "_shared").mkdir(parents=True)

        shutil.copy2(
            source_repo / "config" / "project_config.py",
            isolated_repo / "config" / "project_config.py",
        )
        shutil.copy2(ADD_WRAPPER, isolated_noter / "bin" / ADD_WRAPPER.name)
        shutil.copy2(
            source_repo
            / "research-paper-noter"
            / "skills"
            / "_shared"
            / "user_config.py",
            isolated_noter / "skills" / "_shared" / "user_config.py",
        )
        (
            isolated_noter / "skills" / "_shared" / "user-config.local.json"
        ).write_text(
            json.dumps(
                {
                    "paths": {
                        "domain_paper_folder": "notes",
                        "domain_content_folder": "galleries",
                    }
                }
            ),
            encoding="utf-8",
        )

        capture_path = Path(self.temp_dir.name) / "codex-args.txt"
        fake_codex = Path(self.temp_dir.name) / "fake-codex"
        fake_codex.write_text(
            '#!/usr/bin/env bash\nprintf "%s\\n" "$@" >> "$CAPTURE_PATH"\n',
            encoding="utf-8",
        )
        fake_codex.chmod(0o755)
        markdown_root = Path(self.temp_dir.name) / "markdown-root"
        result = subprocess.run(
            [
                str(isolated_noter / "bin" / ADD_WRAPPER.name),
                self.domain,
                "Parent > Child",
                "Test Paper",
            ],
            env={
                **os.environ,
                "CAPTURE_PATH": str(capture_path),
                "CODEX_BIN": str(fake_codex),
                "RESEARCH_PAPER_CLAW_MARKDOWN_ROOT": str(markdown_root),
            },
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        domain_root = markdown_root / "DomainPapers" / self.domain
        self.assertTrue((domain_root / "notes").is_dir())
        self.assertTrue((domain_root / "galleries").is_dir())
        self.assertFalse((domain_root / "paper").exists())
        self.assertFalse((domain_root / "content").exists())

        captured = capture_path.read_text(encoding="utf-8")
        self.assertIn("CATEGORY_PATH: Parent / Child", captured)
        self.assertIn(f"DOMAIN_PAPERS_PATH: {domain_root / 'notes'}", captured)
        self.assertIn(f"DOMAIN_CONTENT_PATH: {domain_root / 'galleries'}", captured)


if __name__ == "__main__":
    unittest.main()
