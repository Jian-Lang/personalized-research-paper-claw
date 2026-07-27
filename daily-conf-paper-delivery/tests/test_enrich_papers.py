import importlib.util
import tempfile
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


def atom_feed(title: str, arxiv_id: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>{title}</title>
    <id>https://arxiv.org/abs/{arxiv_id}v2</id>
  </entry>
</feed>
"""


def html_search_result(title: str, arxiv_id: str) -> str:
    return f"""
<ol>
  <li class="arxiv-result">
    <p class="list-title is-inline-block">
      <a href="https://arxiv.org/abs/{arxiv_id}">arXiv:{arxiv_id}</a>
    </p>
    <p class="title is-5 mathjax">{title}</p>
  </li>
</ol>
"""


class EnrichPaperTest(unittest.TestCase):
    def test_conference_paper_lookup_adds_arxiv_and_figure(self):
        paper = {
            "title": "Conference Paper",
            "paper_url": "https://conference.example/poster/1",
            "pdf": "https://openreview.net/pdf?id=example",
            "conference": "ICML",
        }

        with mock.patch.object(
            enrich_papers,
            "find_arxiv_by_title",
            return_value=("2607.12345", "https://arxiv.org/abs/2607.12345"),
        ) as find_arxiv, mock.patch.object(
            enrich_papers,
            "extract_first_arxiv_figure",
            return_value="https://arxiv.org/html/2607.12345/x1.png",
        ) as extract_figure:
            normalized = enrich_papers.normalize_paper(paper)

        self.assertEqual(find_arxiv.call_count, 1)
        self.assertEqual(extract_figure.call_count, 1)
        self.assertEqual(normalized["paper_url"], paper["paper_url"])
        self.assertEqual(normalized["pdf"], paper["pdf"])
        self.assertEqual(normalized["arxiv_url"], "https://arxiv.org/abs/2607.12345")
        self.assertEqual(
            normalized["figure_url"], "https://arxiv.org/html/2607.12345/x1.png"
        )

    def test_existing_arxiv_id_skips_title_lookup(self):
        paper = {
            "title": "ArXiv Paper",
            "paper_url": "https://arxiv.org/abs/2607.12345v2",
        }

        with mock.patch.object(enrich_papers, "find_arxiv_by_title") as find_arxiv, mock.patch.object(
            enrich_papers,
            "extract_first_arxiv_figure",
            return_value="https://arxiv.org/html/2607.12345/x1.png",
        ) as extract_figure:
            normalized = enrich_papers.normalize_paper(paper)

        find_arxiv.assert_not_called()
        self.assertEqual(extract_figure.call_args.args, ("2607.12345",))
        self.assertEqual(
            normalized["figure_url"], "https://arxiv.org/html/2607.12345/x1.png"
        )

    def test_network_endpoint_retries_four_times_with_five_second_timeout(self):
        with mock.patch.object(
            enrich_papers.time, "monotonic", return_value=0
        ), mock.patch.object(enrich_papers.time, "sleep") as sleep, mock.patch.object(
            enrich_papers, "fetch_url", return_value=""
        ) as fetch_url:
            result = enrich_papers.fetch_url_with_retry("https://example.test", deadline=20)

        self.assertEqual(result, "")
        self.assertEqual(fetch_url.call_count, 4)
        self.assertEqual(
            [call.kwargs["timeout"] for call in fetch_url.call_args_list],
            [5.0, 5.0, 5.0, 5.0],
        )
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0, 4.0])

    def test_network_endpoint_stops_at_shared_deadline(self):
        now = [0.0]

        def fetch_url_side_effect(_url, *, timeout):
            now[0] += timeout
            return ""

        def sleep_side_effect(delay):
            now[0] += delay

        with mock.patch.object(
            enrich_papers.time, "monotonic", side_effect=lambda: now[0]
        ), mock.patch.object(
            enrich_papers.time, "sleep", side_effect=sleep_side_effect
        ), mock.patch.object(
            enrich_papers, "fetch_url", side_effect=fetch_url_side_effect
        ) as fetch_url:
            result = enrich_papers.fetch_url_with_retry("https://example.test", deadline=12)

        self.assertEqual(result, "")
        self.assertEqual(fetch_url.call_count, 2)
        self.assertEqual(
            [call.kwargs["timeout"] for call in fetch_url.call_args_list],
            [5.0, 5.0],
        )
        self.assertEqual(now[0], 12)

    def test_title_lookup_requires_an_exact_normalized_match(self):
        feed = atom_feed("A Different Conference Paper", "2607.54321")
        with mock.patch.object(enrich_papers.time, "monotonic", return_value=0), mock.patch.object(
            enrich_papers, "fetch_url_with_retry", return_value=feed
        ):
            arxiv_id, arxiv_url = enrich_papers.find_arxiv_by_title(
                "Conference Paper", deadline=20
            )

        self.assertEqual((arxiv_id, arxiv_url), ("", ""))

    def test_title_lookup_accepts_latex_and_punctuation_variants(self):
        feed = atom_feed("Conference Paper: A Study", "2607.54321")
        with mock.patch.object(enrich_papers.time, "monotonic", return_value=0), mock.patch.object(
            enrich_papers, "fetch_url_with_retry", return_value=feed
        ):
            arxiv_id, arxiv_url = enrich_papers.find_arxiv_by_title(
                r"\textbf{Conference Paper}: A Study", deadline=20
            )

        self.assertEqual(arxiv_id, "2607.54321")
        self.assertEqual(arxiv_url, "https://arxiv.org/abs/2607.54321")

    def test_web_search_fallback_requires_an_exact_normalized_match(self):
        raw = html_search_result("Conference Paper: A Study", "2607.54321")

        exact = enrich_papers.exact_html_title_match(
            raw, enrich_papers.normalize_title_key("Conference Paper - A Study")
        )
        mismatch = enrich_papers.exact_html_title_match(
            raw, enrich_papers.normalize_title_key("Different Paper")
        )

        self.assertEqual(exact, ("2607.54321", "https://arxiv.org/abs/2607.54321"))
        self.assertEqual(mismatch, ("", ""))

    def test_title_lookup_uses_web_search_when_api_is_unavailable(self):
        raw = html_search_result("Conference Paper: A Study", "2607.54321")
        with mock.patch.object(
            enrich_papers.time, "monotonic", return_value=0
        ), mock.patch.object(
            enrich_papers, "fetch_url_with_retry", side_effect=["", raw]
        ) as fetch_url:
            match = enrich_papers.find_arxiv_by_title(
                "Conference Paper: A Study", deadline=20
            )

        self.assertEqual(match, ("2607.54321", "https://arxiv.org/abs/2607.54321"))
        self.assertEqual(fetch_url.call_count, 2)

    def test_title_search_lock_wait_respects_the_paper_deadline(self):
        search_lock = mock.Mock()
        search_lock.acquire.return_value = False
        with mock.patch.object(
            enrich_papers.time, "monotonic", return_value=10
        ), mock.patch.object(
            enrich_papers, "ARXIV_SEARCH_LOCK", search_lock
        ), mock.patch.object(enrich_papers, "fetch_url_with_retry") as fetch_url:
            match = enrich_papers.find_arxiv_by_title("Conference Paper", deadline=12)

        self.assertEqual(match, ("", ""))
        search_lock.acquire.assert_called_once_with(timeout=2)
        search_lock.release.assert_not_called()
        fetch_url.assert_not_called()

    def test_failed_lookup_degrades_to_a_paper_without_figure(self):
        paper = {
            "title": "Unavailable Paper",
            "paper_url": "https://conference.example/poster/2",
        }
        with mock.patch.object(
            enrich_papers.time, "monotonic", return_value=0
        ), mock.patch.object(enrich_papers.time, "sleep"), mock.patch.object(
            enrich_papers, "fetch_url", return_value=""
        ) as fetch_url:
            normalized = enrich_papers.normalize_paper(paper)

        self.assertEqual(fetch_url.call_count, 8)
        self.assertEqual(normalized["figure_url"], "")
        self.assertEqual(normalized["paper_url"], paper["paper_url"])
        self.assertTrue(normalized["has_paper"])

    def test_title_and_figure_lookup_share_one_twenty_second_deadline(self):
        with mock.patch.object(enrich_papers.time, "monotonic", return_value=100), mock.patch.object(
            enrich_papers,
            "find_arxiv_by_title",
            return_value=("2607.12345", "https://arxiv.org/abs/2607.12345"),
        ) as find_arxiv, mock.patch.object(
            enrich_papers,
            "extract_first_arxiv_figure",
            return_value="https://arxiv.org/html/2607.12345/x1.png",
        ) as extract_figure:
            enrich_papers.normalize_paper({"title": "Conference Paper"})

        self.assertEqual(find_arxiv.call_args.kwargs["deadline"], 120)
        self.assertEqual(extract_figure.call_args.kwargs["deadline"], 120)

    def test_positive_cache_avoids_repeating_network_requests(self):
        cache = enrich_papers.EnrichmentCache()
        title = "Cached Conference Paper"
        title_key = enrich_papers.normalize_title_key(title)
        cache.remember_title_match(
            title_key, "2607.12345", "https://arxiv.org/abs/2607.12345"
        )
        cache.remember_figure(
            "2607.12345", "https://arxiv.org/html/2607.12345/x1.png"
        )

        with mock.patch.object(enrich_papers, "find_arxiv_by_title") as find_arxiv, mock.patch.object(
            enrich_papers, "extract_first_arxiv_figure"
        ) as extract_figure:
            normalized = enrich_papers.normalize_paper({"title": title}, cache=cache)

        find_arxiv.assert_not_called()
        extract_figure.assert_not_called()
        self.assertEqual(
            normalized["figure_url"], "https://arxiv.org/html/2607.12345/x1.png"
        )

    def test_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "cache.json"
            cache = enrich_papers.EnrichmentCache()
            cache.remember_title_match(
                "paper title", "2607.12345", "https://arxiv.org/abs/2607.12345"
            )
            cache.remember_figure(
                "2607.12345", "https://arxiv.org/html/2607.12345/x1.png"
            )
            cache.save(cache_path)
            restored = enrich_papers.EnrichmentCache.load(cache_path)

        self.assertEqual(
            restored.title_match("paper title"),
            ("2607.12345", "https://arxiv.org/abs/2607.12345"),
        )
        self.assertEqual(
            restored.figure("2607.12345"),
            "https://arxiv.org/html/2607.12345/x1.png",
        )


if __name__ == "__main__":
    unittest.main()
