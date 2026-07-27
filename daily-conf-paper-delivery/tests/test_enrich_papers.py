import importlib.util
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "skills" / "daily-papers" / "enrich_papers.py"
)
SPEC = importlib.util.spec_from_file_location("enrich_papers", MODULE_PATH)
enrich_papers = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(enrich_papers)


class EnrichPaperTest(unittest.TestCase):
    def test_non_arxiv_conference_paper_does_not_trigger_network_lookup(self):
        paper = {
            "title": "Conference Paper",
            "paper_url": "https://conference.example/poster/1",
            "pdf": "https://openreview.net/pdf?id=example",
            "conference": "ICML",
        }

        with mock.patch.object(enrich_papers, "fetch_url") as fetch_url:
            normalized = enrich_papers.normalize_paper(paper)

        fetch_url.assert_not_called()
        self.assertEqual(normalized["paper_url"], paper["paper_url"])
        self.assertEqual(normalized["pdf"], paper["pdf"])
        self.assertTrue(normalized["has_paper"])
        self.assertEqual(normalized["figure_url"], "")

    def test_existing_arxiv_id_can_supply_a_representative_figure(self):
        paper = {
            "title": "ArXiv Paper",
            "paper_url": "https://arxiv.org/abs/2607.12345v2",
        }

        with mock.patch.object(
            enrich_papers,
            "extract_first_arxiv_figure",
            return_value="https://arxiv.org/html/2607.12345/x1.png",
        ) as extract_figure:
            normalized = enrich_papers.normalize_paper(paper)

        extract_figure.assert_called_once_with("2607.12345")
        self.assertEqual(
            normalized["figure_url"], "https://arxiv.org/html/2607.12345/x1.png"
        )
        self.assertTrue(normalized["has_paper"])


if __name__ == "__main__":
    unittest.main()
