from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REBUILD_SCRIPT = SKILL_DIR / "scripts" / "rebuild_domain_gallery.py"
WRAPPER_SCRIPT = SKILL_DIR.parents[1] / "bin" / "domain-paper-gallery-rebuild.sh"


class RebuildDomainGalleryTest(unittest.TestCase):
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

    def write_note(
        self,
        name: str,
        *,
        title: str,
        category: str,
        year: int,
        summary: str,
    ) -> None:
        (self.papers_dir / f"{name}.md").write_text(
            f'''---
title: "{title}"
year: {year}
venue: TestConf
zotero_collection: "{category}"
created: 2026-01-02
---

# {title}

## 元信息

| 链接 | [Paper](https://example.com/{name}) / [PDF](https://example.com/{name}.pdf) |

## 一句话总结

> {summary}

## 论文摘要

- **论文摘要 / English**: Current English abstract for {name}.
- **论文摘要 / 中文**: {name} 的当前中文摘要。

## 问题背景

Current background for {name}.

## 方法详解

Current method for {name}.

## 实验

### 主要结果

Current evaluation for {name}.

## 批判性思考

### 优点

Current significance for {name}.
''',
            encoding="utf-8",
        )

    def write_sidecar(self, pages: dict[str, object]) -> None:
        (self.content_dir / ".domain-papers.json").write_text(
            json.dumps({"pages": pages}, ensure_ascii=False), encoding="utf-8"
        )

    def old_entry(self, *, title: str, note: str, category: str) -> dict[str, object]:
        return {
            "title": title,
            "note": note,
            "year": 2024,
            "venue": "OldConf",
            "url": "https://example.com/old",
            "summary": "Stale summary.",
            "abstract_en": "Stale abstract.",
            "background": "Stale background.",
            "method": "Stale method.",
            "evaluation": "Stale evaluation.",
            "significance": "Stale significance.",
            "related_work": "Preserved relationship.",
            "category_path": category,
            "updated": "2025-01-01",
        }

    def run_rebuild(self, *args: str, wrapper: bool = False) -> subprocess.CompletedProcess[str]:
        command = [str(WRAPPER_SCRIPT)] if wrapper else ["python3", str(REBUILD_SCRIPT)]
        return subprocess.run(
            [*command, *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_rebuilds_all_pages_from_notes_and_preserves_handwritten_content(self) -> None:
        self.write_note(
            "Alpha.v2",
            title="Alpha Updated",
            category="Current / Models",
            year=2026,
            summary="Fresh Alpha summary.",
        )
        self.write_note(
            "Beta",
            title="Beta Paper",
            category="Current / Models",
            year=2025,
            summary="Fresh Beta summary.",
        )
        self.write_sidecar(
            {
                "Legacy.md": {
                    "alpha": self.old_entry(
                        title="Alpha Old", note="Alpha.v2", category="Legacy"
                    ),
                    "deleted": self.old_entry(
                        title="Deleted Paper", note="Deleted", category="Legacy"
                    ),
                }
            }
        )
        legacy_page = self.content_dir / "Legacy.md"
        legacy_page.write_text(
            "# Legacy\n\nKeep this handwritten introduction.\n\n## Papers\n\n"
            "<!-- domain-papers:start -->\nOld block\n<!-- domain-papers:end -->\n",
            encoding="utf-8",
        )

        result = self.run_rebuild("--domain", self.domain)

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["paper_count"], 2)
        current = (self.content_dir / "Current" / "Models.md").read_text(encoding="utf-8")
        self.assertIn("Alpha Updated", current)
        self.assertIn("[[Test Recommendation/paper/Alpha.v2|Alpha.v2]]", current)
        self.assertIn("Stale summary.", current)
        self.assertIn("Stale method.", current)
        self.assertIn("Preserved relationship.", current)
        self.assertIn("Beta Paper", current)
        self.assertIn("Fresh Beta summary.", current)
        self.assertIn("Current method for Beta.", current)
        legacy = legacy_page.read_text(encoding="utf-8")
        self.assertIn("Keep this handwritten introduction.", legacy)
        self.assertIn("暂无论文", legacy)
        self.assertNotIn("Deleted Paper", legacy)
        sidecar = json.loads(
            (self.content_dir / ".domain-papers.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(sidecar["pages"]["Current/Models.md"]), 2)
        self.assertEqual(sidecar["pages"]["Legacy.md"], {})
        self.assertTrue((self.content_dir / "_index.md").is_file())

    def test_wrapper_rebuilds_only_requested_category(self) -> None:
        self.write_note(
            "Alpha",
            title="Alpha Paper",
            category="Selected",
            year=2026,
            summary="Fresh selected summary.",
        )
        self.write_note(
            "Beta",
            title="Beta Paper",
            category="Untouched",
            year=2025,
            summary="Fresh untouched summary.",
        )
        untouched_entry = self.old_entry(
            title="Beta Paper", note="Beta", category="Untouched"
        )
        self.write_sidecar(
            {
                "Selected.md": {
                    "alpha": self.old_entry(
                        title="Alpha Paper", note="Alpha", category="Selected"
                    )
                },
                "Untouched.md": {"beta": untouched_entry},
            }
        )
        untouched_page = self.content_dir / "Untouched.md"
        untouched_page.write_text("# Untouched\n", encoding="utf-8")

        result = self.run_rebuild(self.domain, "Selected", wrapper=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["category_path"], "Selected")
        self.assertEqual(summary["paper_count"], 1)
        selected = (self.content_dir / "Selected.md").read_text(encoding="utf-8")
        self.assertIn("Stale summary.", selected)
        self.assertEqual(untouched_page.read_text(encoding="utf-8"), "# Untouched\n")
        sidecar = json.loads(
            (self.content_dir / ".domain-papers.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sidecar["pages"]["Untouched.md"], {"beta": untouched_entry})


if __name__ == "__main__":
    unittest.main()
