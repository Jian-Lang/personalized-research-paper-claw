#!/usr/bin/env python3
"""Normalize conference paper records for the review step.

The conference adapters already fetch title, authors, abstract, URL, score, and
paper links. This script keeps the existing pipeline shape by reading JSON from
stdin and writing a normalized JSON array to the requested output path.
"""

from __future__ import annotations

import concurrent.futures
import json
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from http.client import IncompleteRead
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


NETWORK_ATTEMPTS = 4
NETWORK_ATTEMPT_TIMEOUT_SECONDS = 5.0
NETWORK_RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
PAPER_NETWORK_BUDGET_SECONDS = 20.0
ENRICHMENT_WORKERS = 3
CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "state" / "arxiv-enrichment-cache.json"
)
ARXIV_SEARCH_LOCK = threading.Lock()

DEFAULTS = {
    "authors": "",
    "affiliations": "",
    "abstract": "",
    "url": "",
    "pdf": "",
    "paper_url": "",
    "arxiv_url": "",
    "date": "",
    "score": 0,
    "status": "",
    "source": "",
    "source_id": "",
    "source_rank": 0,
    "source_rank_display": 0,
    "conference": "",
    "venue": "",
    "year": "",
    "has_paper": False,
    "figure_url": "",
    "section_headers": [],
    "captions": [],
    "has_real_world": False,
    "method_names": [],
    "method_summary": "",
    "score_breakdown": {},
}


class EnrichmentCache:
    def __init__(self, data: dict | None = None) -> None:
        loaded = data if isinstance(data, dict) else {}
        title_matches = loaded.get("title_matches", {})
        figures = loaded.get("figures", {})
        self._title_matches = title_matches if isinstance(title_matches, dict) else {}
        self._figures = figures if isinstance(figures, dict) else {}
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: Path | None = None) -> "EnrichmentCache":
        cache_path = path or CACHE_PATH
        if not cache_path.exists():
            return cls()
        try:
            return cls(json.loads(cache_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:
            print(
                f"  [WARN] ignoring invalid enrichment cache {cache_path}: {exc}",
                file=sys.stderr,
            )
            return cls()

    def title_match(self, title_key: str) -> tuple[str, str] | None:
        with self._lock:
            match = self._title_matches.get(title_key)
            if not isinstance(match, dict):
                return None
            arxiv_id = str(match.get("arxiv_id", "")).strip()
            arxiv_url = str(match.get("arxiv_url", "")).strip()
            return (arxiv_id, arxiv_url) if arxiv_id and arxiv_url else None

    def remember_title_match(
        self, title_key: str, arxiv_id: str, arxiv_url: str
    ) -> None:
        with self._lock:
            self._title_matches[title_key] = {
                "arxiv_id": arxiv_id,
                "arxiv_url": arxiv_url,
            }

    def figure(self, arxiv_id: str) -> str:
        with self._lock:
            return str(self._figures.get(arxiv_id, "")).strip()

    def remember_figure(self, arxiv_id: str, figure_url: str) -> None:
        with self._lock:
            self._figures[arxiv_id] = figure_url

    def save(self, path: Path | None = None) -> None:
        cache_path = path or CACHE_PATH
        with self._lock:
            data = {
                "title_matches": dict(self._title_matches),
                "figures": dict(self._figures),
            }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temp_path.replace(cache_path)
        except OSError as exc:
            print(
                f"  [WARN] could not save enrichment cache {cache_path}: {exc}",
                file=sys.stderr,
            )


class ArxivSearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[tuple[str, str]] = []
        self._inside_result = False
        self._inside_title = False
        self._title_parts: list[str] = []
        self._arxiv_id = ""

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        classes = set(str(attributes.get("class", "")).split())
        if tag == "li" and "arxiv-result" in classes:
            self._inside_result = True
            self._inside_title = False
            self._title_parts = []
            self._arxiv_id = ""
            return
        if not self._inside_result:
            return
        if tag == "p" and "title" in classes:
            self._inside_title = True
        if tag == "a":
            candidate = arxiv_id_from_url(str(attributes.get("href", "")))
            if candidate and not self._arxiv_id:
                self._arxiv_id = candidate

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self._inside_title:
            self._inside_title = False
        if tag == "li" and self._inside_result:
            title = " ".join("".join(self._title_parts).split())
            if title and self._arxiv_id:
                self.results.append((title, self._arxiv_id))
            self._inside_result = False

    def handle_data(self, data: str) -> None:
        if self._inside_result and self._inside_title:
            self._title_parts.append(data)


def strip_tags(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text)


def clean_latex_text(text: str) -> str:
    text = strip_tags(str(text))
    for token in (r"\textit", r"\texttt", r"\textbf", r"\mathbb", r"\mathcal"):
        text = text.replace(token, "")
    text = text.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,")


def normalize_title_key(text: str) -> str:
    text = clean_latex_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def arxiv_id_from_url(url: str) -> str:
    match = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?", str(url))
    return match.group(1) if match else ""


def arxiv_html_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/html/{arxiv_id}"


def fetch_url(url: str, timeout: float = NETWORK_ATTEMPT_TIMEOUT_SECONDS) -> str:
    req = Request(url, headers={"User-Agent": "daily-papers-conference-bot/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except IncompleteRead as e:
        print(f"  [WARN] fetch incomplete {url}: {e}", file=sys.stderr)
        return e.partial.decode("utf-8", errors="replace") if e.partial else ""
    except (HTTPError, URLError, TimeoutError, OSError) as e:
        print(f"  [WARN] fetch failed {url}: {e}", file=sys.stderr)
    return ""


def fetch_url_with_retry(url: str, *, deadline: float) -> str:
    for attempt in range(NETWORK_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        raw = fetch_url(url, timeout=min(NETWORK_ATTEMPT_TIMEOUT_SECONDS, remaining))
        if raw:
            return raw
        if attempt < len(NETWORK_RETRY_BACKOFF_SECONDS):
            remaining = deadline - time.monotonic()
            delay = min(NETWORK_RETRY_BACKOFF_SECONDS[attempt], max(0.0, remaining))
            if delay > 0:
                time.sleep(delay)
    return ""


def exact_atom_title_match(raw: str, target_key: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "", ""

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", namespace):
        entry_title = entry.findtext("atom:title", default="", namespaces=namespace)
        entry_id = entry.findtext("atom:id", default="", namespaces=namespace)
        if normalize_title_key(entry_title) != target_key:
            continue
        arxiv_id = arxiv_id_from_url(entry_id)
        if arxiv_id:
            return arxiv_id, f"https://arxiv.org/abs/{arxiv_id}"
    return "", ""


def exact_html_title_match(raw: str, target_key: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    parser = ArxivSearchHTMLParser()
    try:
        parser.feed(raw)
    except (ValueError, TypeError):
        return "", ""
    for title, arxiv_id in parser.results:
        if normalize_title_key(title) == target_key:
            return arxiv_id, f"https://arxiv.org/abs/{arxiv_id}"
    return "", ""


def find_arxiv_by_title(title: str, *, deadline: float) -> tuple[str, str]:
    clean_title = clean_latex_text(title)
    if not clean_title:
        return "", ""
    target_key = normalize_title_key(clean_title)
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not ARXIV_SEARCH_LOCK.acquire(timeout=remaining):
        return "", ""
    try:
        query = quote(f'ti:"{clean_title}"')
        api_url = (
            "https://export.arxiv.org/api/query?"
            f"search_query={query}&start=0&max_results=5"
        )
        raw = fetch_url_with_retry(api_url, deadline=deadline)
        match = exact_atom_title_match(raw, target_key)
        if match[0]:
            return match

        web_url = (
            "https://arxiv.org/search/?"
            f"query={quote(clean_title)}&searchtype=title&abstracts=hide&"
            "order=-announced_date_first&size=25"
        )
        raw = fetch_url_with_retry(web_url, deadline=deadline)
        return exact_html_title_match(raw, target_key)
    finally:
        ARXIV_SEARCH_LOCK.release()


def normalize_arxiv_image_url(arxiv_id: str, src: str) -> str:
    src = src.strip()
    if not src:
        return ""
    if src.startswith(("http://", "https://")):
        return src
    if src.startswith("/"):
        return urljoin("https://arxiv.org", src)
    # arXiv HTML commonly uses either "x1.png" or "{id}/x1.png".
    first_segment = src.split("/", 1)[0]
    if first_segment.startswith(arxiv_id):
        return urljoin("https://arxiv.org/html/", src)
    return urljoin(f"{arxiv_html_url(arxiv_id)}/", src)


def extract_first_figure_from_html(raw: str, arxiv_id: str, base_url: str) -> str:
    if not raw:
        return ""
    figures = re.findall(
        r"""<figure\b.*?</figure>""",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    search_areas = figures or [raw]
    skip_words = ("icon", "logo", "badge", "inline", "orcid", "creative")
    for area in search_areas:
        img_match = re.search(
            r"""<img\b[^>]*\bsrc=["']([^"']+)["']""",
            area,
            flags=re.IGNORECASE,
        )
        if not img_match:
            continue
        src = img_match.group(1).strip()
        if any(word in src.lower() for word in skip_words):
            continue
        if base_url.startswith("https://arxiv.org/html/"):
            return normalize_arxiv_image_url(arxiv_id, src)
        return urljoin(f"{base_url.rstrip('/')}/", src)
    return ""


def extract_first_arxiv_figure(arxiv_id: str, *, deadline: float | None = None) -> str:
    if not arxiv_id:
        return ""
    if deadline is None:
        deadline = time.monotonic() + PAPER_NETWORK_BUDGET_SECONDS

    arxiv_html = arxiv_html_url(arxiv_id)
    raw = fetch_url_with_retry(arxiv_html, deadline=deadline)
    figure_url = extract_first_figure_from_html(raw, arxiv_id, arxiv_html)
    if figure_url:
        return figure_url

    ar5iv_html = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    raw = fetch_url_with_retry(ar5iv_html, deadline=deadline)
    if "No content available" in raw[:1000]:
        return ""
    return extract_first_figure_from_html(raw, arxiv_id, ar5iv_html)


def enrich_arxiv_assets(
    paper: dict,
    *,
    deadline: float | None = None,
    cache: EnrichmentCache | None = None,
) -> dict:
    if paper.get("figure_url"):
        return paper
    if deadline is None:
        deadline = time.monotonic() + PAPER_NETWORK_BUDGET_SECONDS

    arxiv_id = (
        arxiv_id_from_url(paper.get("paper_url", ""))
        or arxiv_id_from_url(paper.get("pdf", ""))
        or arxiv_id_from_url(paper.get("url", ""))
    )
    if not arxiv_id:
        title_key = normalize_title_key(paper.get("title", ""))
        match = cache.title_match(title_key) if cache and title_key else None
        if match:
            arxiv_id, arxiv_url = match
        else:
            arxiv_id, arxiv_url = find_arxiv_by_title(
                paper.get("title", ""), deadline=deadline
            )
            if arxiv_id and cache and title_key:
                cache.remember_title_match(title_key, arxiv_id, arxiv_url)
        if arxiv_id:
            paper["arxiv_url"] = arxiv_url
            if not paper.get("pdf"):
                paper["pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
            paper["has_paper"] = True

    if arxiv_id:
        figure_url = cache.figure(arxiv_id) if cache else ""
        if not figure_url:
            figure_url = extract_first_arxiv_figure(arxiv_id, deadline=deadline)
            if figure_url and cache:
                cache.remember_figure(arxiv_id, figure_url)
        paper["figure_url"] = figure_url
    return paper


def normalize_paper(paper: dict, *, cache: EnrichmentCache | None = None) -> dict:
    normalized = dict(DEFAULTS)
    normalized.update(paper)
    normalized["has_paper"] = bool(
        normalized.get("has_paper")
        or normalized.get("pdf")
        or normalized.get("paper_url")
    )
    deadline = time.monotonic() + PAPER_NETWORK_BUDGET_SECONDS
    return enrich_arxiv_assets(normalized, deadline=deadline, cache=cache)


def normalize_papers(papers: list[dict], cache: EnrichmentCache) -> list[dict]:
    valid_papers = [paper for paper in papers if isinstance(paper, dict)]
    if not valid_papers:
        return []
    workers = min(ENRICHMENT_WORKERS, len(valid_papers))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        return list(
            executor.map(
                lambda paper: normalize_paper(paper, cache=cache), valid_papers
            )
        )


def count_figures(papers: list[dict]) -> int:
    return sum(1 for paper in papers if paper.get("figure_url"))


def write_output(data: str, output_path: str | None) -> None:
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(data)
    else:
        sys.stdout.write(data)
        sys.stdout.flush()


def main() -> int:
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    raw = sys.stdin.read()
    if not raw.strip():
        write_output("[]\n", output_path)
        return 0

    try:
        papers = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        write_output("[]\n", output_path)
        return 1

    if not isinstance(papers, list):
        print("JSON input must be an array", file=sys.stderr)
        write_output("[]\n", output_path)
        return 1

    cache = EnrichmentCache.load()
    normalized = normalize_papers(papers, cache)
    cache.save()
    write_output(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", output_path)
    print(
        f"Normalized {len(normalized)} conference papers; "
        f"{count_figures(normalized)} with figure_url.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
