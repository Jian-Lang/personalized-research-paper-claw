import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "skills" / "daily-papers" / "fetch_and_score.py"
SPEC = importlib.util.spec_from_file_location("fetch_and_score", MODULE_PATH)
fetch_and_score = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(fetch_and_score)


class ScorePaperTest(unittest.TestCase):
    def setUp(self):
        self.original = (
            fetch_and_score.TOPICS,
            fetch_and_score.KEYWORDS,
            fetch_and_score.EXCLUDE_KEYWORDS,
        )
        fetch_and_score.TOPICS = ["LLM Abstention"]
        fetch_and_score.KEYWORDS = ["admit uncertainty"]
        fetch_and_score.EXCLUDE_KEYWORDS = ["medical"]

    def tearDown(self):
        (
            fetch_and_score.TOPICS,
            fetch_and_score.KEYWORDS,
            fetch_and_score.EXCLUDE_KEYWORDS,
        ) = self.original

    def test_topic_match_adds_one(self):
        paper = {"title": "A Study of LLM Abstention", "abstract": ""}
        self.assertEqual(fetch_and_score.score_paper(paper), 1)
        self.assertEqual(paper["score_breakdown"]["topics"], ["LLM Abstention"])

    def test_title_keyword_adds_three(self):
        paper = {"title": "Teaching Models to Admit Uncertainty", "abstract": ""}
        self.assertEqual(fetch_and_score.score_paper(paper), 3)
        self.assertEqual(paper["score_breakdown"]["title_keywords"], ["admit uncertainty"])

    def test_abstract_keyword_adds_one(self):
        paper = {"title": "Reliable Models", "abstract": "The model learns to admit uncertainty."}
        self.assertEqual(fetch_and_score.score_paper(paper), 1)
        self.assertEqual(paper["score_breakdown"]["abstract_keywords"], ["admit uncertainty"])

    def test_topic_and_abstract_keyword_reach_default_threshold(self):
        paper = {
            "title": "Reliable Models",
            "abstract": "LLM abstention teaches a model to admit uncertainty.",
        }
        self.assertEqual(fetch_and_score.score_paper(paper), 2)

    def test_exclude_keyword_is_hard_filter(self):
        paper = {
            "title": "Medical Models That Admit Uncertainty",
            "abstract": "This work studies LLM abstention.",
        }
        self.assertEqual(fetch_and_score.score_paper(paper), -100)
        self.assertEqual(paper["score_breakdown"]["excluded_by"], ["medical"])

    def test_matching_uses_whole_term_boundaries(self):
        fetch_and_score.TOPICS = []
        fetch_and_score.KEYWORDS = ["UMM"]
        paper = {"title": "Learning to Control Summaries with Score Ranking", "abstract": ""}
        self.assertEqual(fetch_and_score.score_paper(paper), 0)

    def test_equivalent_terms_are_deduplicated(self):
        terms = fetch_and_score.unique_terms(["test-time adaptation", "Test Time Adaptation"])
        self.assertEqual(terms, ["test-time adaptation"])


class ConferenceSourceTest(unittest.TestCase):
    def setUp(self):
        self.original_conferences = fetch_and_score.CONFIG.get("conferences")

    def tearDown(self):
        if self.original_conferences is None:
            fetch_and_score.CONFIG.pop("conferences", None)
        else:
            fetch_and_score.CONFIG["conferences"] = self.original_conferences

    def test_custom_conference_uses_local_snapshot_convention(self):
        fetch_and_score.CONFIG["conferences"] = [
            {"name": "NeurIPS", "year": 2026, "daily_take": 4}
        ]

        sources = fetch_and_score.resolve_conference_sources()

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "NEURIPS")
        self.assertEqual(sources[0]["snapshot_path"], "NEURIPS/neurips_2026.jsonl")
        self.assertNotIn("url", sources[0])
        self.assertNotIn("page_url", sources[0])


if __name__ == "__main__":
    unittest.main()
