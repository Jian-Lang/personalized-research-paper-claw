#!/usr/bin/env python3
"""Normalize conference paper records for the review step.

The conference adapters already fetch title, authors, abstract, URL, score, and
paper links. This script keeps the existing pipeline shape by reading JSON from
stdin and writing a normalized JSON array to the requested output path.
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from http.client import IncompleteRead
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen


DEFAULTS = {
    "authors": "",
    "affiliations": "",
    "abstract": "",
    "url": "",
    "pdf": "",
    "paper_url": "",
    "date": "",
    "score": 0,
    "category": "",
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
}


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


def fetch_url(url: str, timeout: int = 30) -> str:
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


def find_arxiv_by_title(title: str) -> tuple[str, str]:
    """Find an exact arXiv title match for conference papers linked elsewhere."""
    clean_title = clean_latex_text(title)
    if not clean_title:
        return "", ""
    query = quote(f'ti:"{clean_title}"')
    url = f"https://export.arxiv.org/api/query?search_query={query}&start=0&max_results=5"
    raw = fetch_url(url, timeout=20)
    if not raw:
        return "", ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "", ""

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    target_key = normalize_title_key(clean_title)
    for entry in root.findall("atom:entry", ns):
        entry_title = entry.findtext("atom:title", default="", namespaces=ns)
        entry_id = entry.findtext("atom:id", default="", namespaces=ns)
        if normalize_title_key(entry_title) != target_key:
            continue
        arxiv_id = arxiv_id_from_url(entry_id)
        if arxiv_id:
            return arxiv_id, f"https://arxiv.org/abs/{arxiv_id}"
    return "", ""


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
        img_match = re.search(r"""<img\b[^>]*\bsrc=["']([^"']+)["']""", area, flags=re.IGNORECASE)
        if not img_match:
            continue
        src = img_match.group(1).strip()
        if any(word in src.lower() for word in skip_words):
            continue
        if base_url.startswith("https://arxiv.org/html/"):
            return normalize_arxiv_image_url(arxiv_id, src)
        return urljoin(f"{base_url.rstrip('/')}/", src)
    return ""


def extract_first_arxiv_figure(arxiv_id: str) -> str:
    if not arxiv_id:
        return ""

    arxiv_html = arxiv_html_url(arxiv_id)
    raw = fetch_url(arxiv_html, timeout=30)
    figure_url = extract_first_figure_from_html(raw, arxiv_id, arxiv_html)
    if figure_url:
        return figure_url

    ar5iv_html = f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"
    raw = fetch_url(ar5iv_html, timeout=30)
    if "No content available" in raw[:1000]:
        return ""
    return extract_first_figure_from_html(raw, arxiv_id, ar5iv_html)


def enrich_arxiv_assets(paper: dict) -> dict:
    arxiv_id = (
        arxiv_id_from_url(paper.get("paper_url", ""))
        or arxiv_id_from_url(paper.get("pdf", ""))
        or arxiv_id_from_url(paper.get("url", ""))
    )
    if not arxiv_id and not paper.get("figure_url"):
        arxiv_id, arxiv_url = find_arxiv_by_title(paper.get("title", ""))
        if arxiv_id:
            # Preserve the original conference/OpenReview page, but fill arXiv
            # as the PDF source so downstream review can expose a readable paper.
            paper.setdefault("paper_url", arxiv_url)
            if not arxiv_id_from_url(paper.get("paper_url", "")):
                paper["arxiv_url"] = arxiv_url
            if not paper.get("pdf") or "openreview.net/pdf" in str(paper.get("pdf", "")):
                paper["pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
            paper["has_paper"] = True

    if arxiv_id and not paper.get("figure_url"):
        paper["figure_url"] = extract_first_arxiv_figure(arxiv_id)
    return paper


def normalize_paper(paper: dict) -> dict:
    normalized = dict(DEFAULTS)
    normalized.update(paper)
    normalized["has_paper"] = bool(normalized.get("has_paper") or normalized.get("pdf") or normalized.get("paper_url"))
    return enrich_arxiv_assets(normalized)


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

    normalized = [normalize_paper(paper) for paper in papers if isinstance(paper, dict)]
    write_output(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", output_path)
    print(
        f"Normalized {len(normalized)} conference papers; "
        f"{count_figures(normalized)} with figure_url.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
