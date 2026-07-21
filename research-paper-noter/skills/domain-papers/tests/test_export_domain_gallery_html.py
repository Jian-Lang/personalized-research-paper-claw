from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = SKILL_DIR / "scripts" / "export_domain_gallery_html.py"
WRAPPER_SCRIPT = SKILL_DIR.parents[1] / "bin" / "domain-paper-gallery-html.sh"


class ExportDomainGalleryHtmlTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault = Path(self.temp_dir.name) / "DomainPapers"
        self.domain = "Test & Recommendation"
        self.domain_dir = self.vault / self.domain
        self.content_dir = self.domain_dir / "content"
        self.papers_dir = self.domain_dir / "paper"
        (self.papers_dir / "assets").mkdir(parents=True)
        self.content_dir.mkdir(parents=True)
        (self.papers_dir / "assets" / "teaser.png").write_bytes(b"test-image")
        self.env = {**os.environ, "DOMAIN_PAPERS_VAULT": str(self.vault)}
        self.write_sidecar()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_sidecar(self) -> None:
        pages = {
            "LLM-based Recommendation.md": {
                "older": self.entry(
                    title="Older <Paper>",
                    note="OlderNote",
                    year=2024,
                    figure="![[assets/teaser.png]]",
                    category="LLM-based Recommendation",
                ),
                "newer": self.entry(
                    title="Newer & Safer",
                    note="NewerNote",
                    year=2026,
                    published_date="2026-02-03",
                    url="javascript:alert(1)",
                    figure="![Remote](https://example.com/figure.png)",
                    category="LLM-based Recommendation",
                ),
            },
            "Memory/Long-Term.md": {
                "memory": self.entry(
                    title="Memory Paper",
                    note="MemoryNote",
                    year=2025,
                    url="https://example.com/paper?a=1&b=2",
                    category="Memory / Long-Term",
                )
            },
        }
        (self.content_dir / ".domain-papers.json").write_text(
            json.dumps({"pages": pages}, ensure_ascii=False), encoding="utf-8"
        )

    def entry(
        self,
        *,
        title: str,
        note: str,
        year: int,
        category: str,
        published_date: str = "",
        url: str = "https://example.com/paper",
        figure: str = "",
    ) -> dict[str, object]:
        return {
            "title": title,
            "note": note,
            "year": year,
            "venue": "TestConf",
            "url": url,
            "published_date": published_date,
            "summary": "One sentence.",
            "abstract_en": "English abstract.",
            "background": "Background.",
            "method": "Method.",
            "evaluation": "Evaluation.",
            "significance": "Significance.",
            "related_work": "Related work.",
            "figure": figure,
            "category_path": category,
        }

    def run_export(self, *args: str, wrapper: bool = False) -> subprocess.CompletedProcess[str]:
        command = [str(WRAPPER_SCRIPT)] if wrapper else ["python3", str(EXPORT_SCRIPT)]
        return subprocess.run(
            [*command, *args],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_exports_all_subdomains_and_copies_local_assets(self) -> None:
        output = Path(self.temp_dir.name) / "share" / "gallery.html"
        result = self.run_export(
            "--domain", self.domain, "--output", str(output)
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["paper_count"], 3)
        self.assertEqual(summary["source_page_count"], 2)
        self.assertEqual(summary["copied_asset_count"], 1)

        rendered = output.read_text(encoding="utf-8")
        self.assertIn("Test &amp; Recommendation", rendered)
        self.assertIn("LLM-based Recommendation", rendered)
        self.assertIn("Memory / Long-Term", rendered)
        self.assertIn("Older &lt;Paper&gt;", rendered)
        self.assertLess(rendered.index("Newer &amp; Safer"), rendered.index("Memory Paper"))
        self.assertLess(rendered.index("Memory Paper"), rendered.index("Older &lt;Paper&gt;"))
        self.assertIn("https://example.com/figure.png", rendered)
        self.assertIn("gallery-assets/03-teaser.png", rendered)
        self.assertNotIn("javascript:alert", rendered)
        self.assertTrue((output.parent / "gallery-assets" / "03-teaser.png").is_file())

    def test_wrapper_exports_only_requested_nested_category(self) -> None:
        result = self.run_export(
            self.domain, "Memory > Long-Term", wrapper=True
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        output = Path(summary["html_path"])
        self.assertEqual(output, self.domain_dir / "html" / "memory-long-term.html")
        rendered = output.read_text(encoding="utf-8")
        self.assertIn("Memory Paper", rendered)
        self.assertNotIn("Older &lt;Paper&gt;", rendered)
        self.assertEqual(summary["source_page_count"], 1)
        self.assertEqual(summary["paper_count"], 1)

    def test_missing_category_reports_available_categories(self) -> None:
        result = self.run_export(
            "--domain", self.domain, "--category-path", "Unknown"
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("category Gallery not found: Unknown", result.stderr)
        self.assertIn("LLM-based Recommendation", result.stderr)
        self.assertIn("Memory / Long-Term", result.stderr)


if __name__ == "__main__":
    unittest.main()
