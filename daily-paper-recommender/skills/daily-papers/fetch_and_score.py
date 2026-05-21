#!/usr/bin/env python3
"""
fetch_and_score.py — conference paper fetcher for daily recommendations.

The daily recommender is conference-only. It scans configured acceptance lists
from a saved cursor, reads title + abstract from each detail page, scores by
user keywords, and emits the next matching papers as JSON.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen

_SHARED_DIR = Path(__file__).resolve().parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import daily_papers_config, daily_project_dir


CONFIG = daily_papers_config()
CONFERENCE_PREFS = CONFIG.get("conference_preferences", {})
KEYWORDS = CONFERENCE_PREFS.get("keywords", [])
NEGATIVE_KEYWORDS = CONFERENCE_PREFS.get("negative_keywords", [])
MIN_SCORE = int(CONFERENCE_PREFS.get("min_score", 2))
PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFERENCE_STATE_PATH = PROJECT_DIR / "state" / "conference-state.json"
LEGACY_CONFERENCE_STATE_PATH = daily_project_dir() / ".conference-state.json"
DEFAULT_DAILY_TAKE = 5
DEFAULT_SCAN_LIMIT = 120

CONFERENCE_REGISTRY = {
    "icml": {
        "name": "ICML",
        "type": "icml_downloads",
        "url_template": "https://icml.cc/Downloads/{year}",
    },
    "iclr": {
        "name": "ICLR",
        "type": "papers_cool_venue",
        "url_template": "https://papers.cool/venue/ICLR.{year}",
    },
}


def configured_daily_take(source: dict) -> int:
    return int(source.get("daily_take") or CONFIG.get("daily_take") or DEFAULT_DAILY_TAKE)


def configured_scan_limit(source: dict) -> int:
    return int(source.get("scan_window") or CONFIG.get("scan_limit") or DEFAULT_SCAN_LIMIT)


def strip_tags(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text)


def clean_html_text(html_text: str) -> str:
    text = strip_tags(html_text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,")


def clean_latex_text(text: str) -> str:
    text = html.unescape(strip_tags(text))
    for token in (r"\textit", r"\texttt", r"\textbf", r"\mathbb", r"\mathcal"):
        text = text.replace(token, "")
    text = text.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,")


def normalize_title_key(text: str) -> str:
    text = clean_latex_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, html.unescape(href.strip()))


def url_with_query(url: str, **params) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        query[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def arxiv_id_from_url(url: str) -> str:
    match = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?", url)
    return match.group(1) if match else ""


def arxiv_html_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/html/{arxiv_id}"


def extract_first_arxiv_figure(arxiv_id: str) -> str:
    if not arxiv_id:
        return ""
    raw, _, _ = fetch_url_detailed(arxiv_html_url(arxiv_id), timeout=30, retries=0)
    if not raw:
        return ""
    figure_match = re.search(r"""<figure\b.*?</figure>""", raw, flags=re.DOTALL | re.IGNORECASE)
    search_area = figure_match.group(0) if figure_match else raw
    img_match = re.search(r"""<img\b[^>]*\bsrc=["']([^"']+)["']""", search_area, flags=re.IGNORECASE)
    if not img_match:
        return ""
    return urljoin(f"{arxiv_html_url(arxiv_id)}/", html.unescape(img_match.group(1).strip()))


def find_arxiv_by_title(title: str) -> tuple[str, str]:
    query = quote(f'ti:"{title}"')
    url = f"https://export.arxiv.org/api/query?search_query={query}&start=0&max_results=3"
    raw, _, _ = fetch_url_detailed(url, timeout=20, retries=0)
    if not raw:
        return "", ""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return "", ""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    target_key = normalize_title_key(title)
    for entry in root.findall("atom:entry", ns):
        entry_title = entry.findtext("atom:title", default="", namespaces=ns)
        entry_id = entry.findtext("atom:id", default="", namespaces=ns)
        if normalize_title_key(entry_title) != target_key:
            continue
        arxiv_id = arxiv_id_from_url(entry_id)
        if arxiv_id:
            return arxiv_id, f"https://arxiv.org/abs/{arxiv_id}"
    return "", ""


def fetch_url_detailed(url: str, timeout: int = 30, retries: int = 1) -> tuple[str, int | None, str]:
    req = Request(url, headers={"User-Agent": "daily-papers-conference-bot/1.0"})
    last_error = ""
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                return resp.read().decode("utf-8", errors="replace"), status, ""
        except HTTPError as e:
            last_error = str(e)
            if attempt >= retries:
                print(f"  [WARN] fetch failed {url}: {e}", file=sys.stderr)
                return "", e.code, last_error
        except URLError as e:
            last_error = str(e)
            if attempt >= retries:
                print(f"  [WARN] fetch failed {url}: {e}", file=sys.stderr)
                return "", None, last_error
        except Exception as e:
            last_error = str(e)
            if attempt >= retries:
                print(f"  [WARN] fetch failed {url}: {e}", file=sys.stderr)
                return "", None, last_error
    return "", None, last_error


def score_paper(paper: dict) -> int:
    title = paper.get("title", "").lower()
    abstract = paper.get("abstract", "").lower()
    score = 0
    for keyword in NEGATIVE_KEYWORDS:
        kw = str(keyword).strip().lower()
        if not kw:
            continue
        if kw in title or kw in abstract:
            score -= 100
    for keyword in KEYWORDS:
        kw = str(keyword).strip().lower()
        if not kw:
            continue
        if kw in title:
            score += 2
        elif kw in abstract:
            score += 1
    return score


def paper_unique_id(paper: dict) -> str:
    if paper.get("source_id"):
        return str(paper["source_id"])
    title_key = re.sub(r"[^a-z0-9]+", "-", paper.get("title", "").lower()).strip("-")
    return title_key[:120]


def resolve_conference_sources() -> list[dict]:
    if "conference_sources" in CONFIG:
        return [source for source in CONFIG.get("conference_sources", []) if source.get("enabled", True)]

    configured = CONFIG.get("conferences")
    if configured is None:
        configured = [CONFIG.get("conference", {})]
    elif isinstance(configured, dict):
        configured = [configured]

    sources = []
    for conference in configured:
        if not isinstance(conference, dict) or not conference.get("enabled", True):
            continue
        name = str(conference.get("name", "")).strip()
        year = int(conference.get("year", 0) or 0)
        registry_entry = CONFERENCE_REGISTRY.get(name.lower())
        if not registry_entry:
            print(f"  [WARN] unsupported conference: {name} {year}", file=sys.stderr)
            continue

        source = dict(registry_entry)
        source["name"] = registry_entry.get("name", name.upper())
        source["year"] = year
        source["url"] = registry_entry["url_template"].format(year=year)
        source["enabled"] = True
        sources.append(source)
    return sources


def conference_source_key(source: dict) -> str:
    name = str(source.get("name", "")).strip().lower()
    year = str(source.get("year", "")).strip()
    source_type = str(source.get("type", "")).strip().lower()
    return "-".join(part for part in (source_type or name, name, year) if part)


def load_conference_state() -> dict:
    state_path = CONFERENCE_STATE_PATH if CONFERENCE_STATE_PATH.exists() else LEGACY_CONFERENCE_STATE_PATH
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("sources", {})
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"sources": {}}


def write_conference_state(state: dict) -> None:
    try:
        CONFERENCE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFERENCE_STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"  [WARN] failed to write conference state {CONFERENCE_STATE_PATH}: {e}", file=sys.stderr)


def parse_json_ld(html_text: str) -> dict:
    for raw in re.findall(
        r"""<script[^>]+type=["']application/ld\+json["'][^>]*>(.*?)</script>""",
        html_text,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return {}


def parse_icml_downloads(html_text: str, source: dict) -> list[dict]:
    base_url = source["url"]
    conference = str(source.get("name", "ICML")).strip() or "ICML"
    year = int(source.get("year", 0) or 0)
    seen_ids: set[str] = set()
    papers = []
    pattern = r"""<a\b[^>]*href=["']([^"']*/virtual/\d+/poster/(\d+)[^"']*)["'][^>]*>(.*?)</a>"""
    for href, poster_id, raw_title in re.findall(pattern, html_text, flags=re.DOTALL | re.IGNORECASE):
        if poster_id in seen_ids:
            continue
        seen_ids.add(poster_id)
        title = clean_latex_text(raw_title)
        if not title:
            continue
        rank = len(papers)
        detail_url = absolute_url(base_url, href)
        papers.append(
            {
                "title": title,
                "authors": "",
                "affiliations": "",
                "abstract": "",
                "url": detail_url,
                "pdf": "",
                "paper_url": "",
                "date": "",
                "score": 0,
                "category": "",
                "source": "conference-icml",
                "source_id": f"{conference.lower()}-{year}-{poster_id}",
                "source_rank": rank,
                "source_rank_display": rank + 1,
                "conference": conference,
                "venue": f"{conference} {year}" if year else conference,
                "year": year,
                "poster_id": poster_id,
                "has_paper": False,
                "figure_url": "",
                "section_headers": [],
                "captions": [],
                "has_real_world": False,
                "method_names": [],
                "method_summary": "",
            }
        )
    return papers


def make_conference_paper(
    *,
    source: dict,
    source_kind: str,
    source_id_suffix: str,
    title: str,
    authors: str,
    abstract: str,
    url: str,
    pdf: str,
    paper_url: str,
    rank: int,
    category: str = "",
    date: str = "",
) -> dict:
    conference = str(source.get("name", "")).strip() or "Conference"
    year = int(source.get("year", 0) or 0)
    source_slug = re.sub(r"[^a-z0-9]+", "-", conference.lower()).strip("-") or "conference"
    return {
        "title": title,
        "authors": authors,
        "affiliations": "",
        "abstract": abstract,
        "url": url,
        "pdf": pdf,
        "paper_url": paper_url,
        "date": date,
        "score": 0,
        "category": category,
        "source": f"conference-{source_slug}",
        "source_id": f"{source_slug}-{year}-{source_id_suffix}",
        "source_rank": rank,
        "source_rank_display": rank + 1,
        "conference": conference,
        "venue": f"{conference} {year}" if year else conference,
        "year": year,
        "poster_id": source_id_suffix,
        "has_paper": bool(paper_url or pdf),
        "figure_url": "",
        "section_headers": [],
        "captions": [],
        "has_real_world": False,
        "method_names": [],
        "method_summary": "",
        "source_kind": source_kind,
    }


def extract_first_link(block: str, pattern: str, base_url: str = "") -> str:
    match = re.search(pattern, block, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    href = html.unescape(match.group(1).strip())
    return absolute_url(base_url, href) if base_url else href


def parse_papers_cool_venue(html_text: str, source: dict) -> list[dict]:
    base_url = source["url"]
    papers = []
    pattern = r"""<div\b[^>]*\bid=["']([^"']+)["'][^>]*\bclass=["'][^"']*\bpaper\b[^"']*["'][^>]*>(.*?)</div>\s*(?=<div\b[^>]*\bid=|</div>\s*</body>)"""
    for raw_id, block in re.findall(pattern, html_text, flags=re.DOTALL | re.IGNORECASE):
        title_match = re.search(
            r"""<a\b[^>]*\bclass=["'][^"']*\btitle-link\b[^"']*["'][^>]*\bhref=["']([^"']+)["'][^>]*>(.*?)</a>""",
            block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        if not title_match:
            continue
        detail_url = absolute_url(base_url, title_match.group(1))
        title = clean_latex_text(title_match.group(2))
        if not title:
            continue

        rank_match = re.search(r"""<span\b[^>]*\bclass=["'][^"']*\bindex\b[^"']*["'][^>]*>#?(\d+)</span>""", block)
        rank = int(rank_match.group(1)) - 1 if rank_match else len(papers)
        openreview_url = extract_first_link(block, r"""<h2[^>]*>.*?<a\b[^>]*\bhref=["'](https://openreview\.net/forum\?id=[^"']+)["']""")
        pdf_url = extract_first_link(block, r"""<a\b[^>]*\bclass=["'][^"']*\btitle-pdf\b[^"']*["'][^>]*\bdata=["']([^"']+)["']""", base_url)

        authors_match = re.search(
            r"""<p\b[^>]*\bclass=["'][^"']*\bauthors\b[^"']*["'][^>]*>(.*?)</p>""",
            block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        authors = clean_html_text(authors_match.group(1)).removeprefix("Authors:").strip() if authors_match else ""
        summary_match = re.search(
            r"""<p\b[^>]*\bclass=["'][^"']*\bsummary\b[^"']*["'][^>]*>(.*?)</p>""",
            block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        abstract = clean_latex_text(summary_match.group(1)) if summary_match else ""
        subject_match = re.search(
            r"""<p\b[^>]*\bclass=["'][^"']*\bsubjects\b[^"']*["'][^>]*>(.*?)</p>""",
            block,
            flags=re.DOTALL | re.IGNORECASE,
        )
        category = clean_html_text(subject_match.group(1)).removeprefix("Subject:").strip() if subject_match else ""
        source_id_suffix = re.sub(r"[^A-Za-z0-9_-]+", "-", html.unescape(raw_id)).strip("-") or paper_unique_id({"title": title})
        papers.append(
            make_conference_paper(
                source=source,
                source_kind="papers_cool_venue",
                source_id_suffix=source_id_suffix,
                title=title,
                authors=authors,
                abstract=abstract,
                url=detail_url,
                pdf=pdf_url,
                paper_url=openreview_url or detail_url,
                rank=rank,
                category=category,
            )
        )
    return sorted(papers, key=lambda paper: paper.get("source_rank", 10**9))


def fetch_papers_cool_stubs(source: dict, cursor: int, scan_end: int) -> list[dict]:
    page_size = int(source.get("page_size") or 25)
    first_skip = (cursor // page_size) * page_size
    stubs: list[dict] = []
    seen_ids: set[str] = set()

    for skip in range(first_skip, scan_end, page_size):
        page_url = source["url"] if skip == 0 else url_with_query(source["url"], skip=skip)
        raw, _, _ = fetch_url_detailed(page_url, timeout=45, retries=1)
        if not raw:
            break
        page_stubs = parse_papers_cool_venue(raw, source)
        if not page_stubs:
            break
        for paper in page_stubs:
            rank = int(paper.get("source_rank", 10**9))
            pid = paper_unique_id(paper)
            if cursor <= rank < scan_end and pid not in seen_ids:
                stubs.append(paper)
                seen_ids.add(pid)
        if len(page_stubs) < page_size:
            break

    return sorted(stubs, key=lambda paper: paper.get("source_rank", 10**9))


def extract_icml_links(html_text: str, detail_url: str) -> tuple[str, str]:
    paper_url = ""
    pdf_url = ""
    for href in re.findall(r"""href=["']([^"']+)["']""", html_text, flags=re.IGNORECASE):
        full_url = absolute_url(detail_url, href)
        low = full_url.lower()
        if "openreview.net" in low or "arxiv.org/abs/" in low:
            paper_url = paper_url or full_url
        if low.endswith(".pdf") or "/pdf/" in low or "arxiv.org/pdf/" in low:
            pdf_url = pdf_url or full_url
            paper_url = paper_url or full_url
    return paper_url, pdf_url


def enrich_icml_detail(stub: dict) -> dict:
    paper = dict(stub)
    detail_url = paper["url"]
    raw, _, _ = fetch_url_detailed(detail_url, timeout=30, retries=1)
    if not raw:
        paper["score"] = score_paper(paper)
        return paper

    json_ld = parse_json_ld(raw)
    if json_ld.get("name"):
        paper["title"] = clean_latex_text(str(json_ld["name"]))
    authors = []
    for author in json_ld.get("author", []) if isinstance(json_ld.get("author"), list) else []:
        if isinstance(author, dict) and author.get("name"):
            authors.append(str(author["name"]).strip())
    if authors:
        paper["authors"] = ", ".join(authors)
    if json_ld.get("datePublished"):
        paper["date"] = str(json_ld["datePublished"])[:10]

    title_match = re.search(
        r"""<h1[^>]+class=["'][^"']*event-title[^"']*["'][^>]*>(.*?)</h1>""",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if title_match:
        paper["title"] = clean_latex_text(title_match.group(1))

    authors_match = re.search(
        r"""<div[^>]+class=["'][^"']*event-organizers[^"']*["'][^>]*>(.*?)</div>""",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if authors_match:
        paper["authors"] = clean_html_text(authors_match.group(1)).replace(" ⋅ ", ", ")

    abstract_match = re.search(
        r"""<div[^>]+class=["'][^"']*abstract-text-inner[^"']*["'][^>]*>(.*?)</div>""",
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if abstract_match:
        paper["abstract"] = clean_latex_text(abstract_match.group(1))

    keywords_match = re.search(
        r"""<meta[^>]+name=["']keywords["'][^>]+content=["']([^"']+)["']""",
        raw,
        flags=re.IGNORECASE,
    )
    if keywords_match:
        paper["category"] = clean_html_text(keywords_match.group(1))

    paper_url, pdf_url = extract_icml_links(raw, detail_url)
    paper["paper_url"] = paper_url
    paper["pdf"] = pdf_url
    paper["has_paper"] = bool(paper_url or pdf_url)
    paper["score"] = score_paper(paper)
    return paper


def enrich_selected_paper_assets(paper: dict) -> dict:
    paper = dict(paper)
    arxiv_id = arxiv_id_from_url(paper.get("paper_url", "")) or arxiv_id_from_url(paper.get("pdf", ""))
    if not arxiv_id and not paper.get("paper_url") and not paper.get("pdf"):
        arxiv_id, arxiv_url = find_arxiv_by_title(paper.get("title", ""))
        if arxiv_id:
            paper["paper_url"] = arxiv_url
            paper["pdf"] = f"https://arxiv.org/pdf/{arxiv_id}"
            paper["has_paper"] = True
    if arxiv_id and not paper.get("figure_url"):
        paper["figure_url"] = extract_first_arxiv_figure(arxiv_id)
    return paper


def enrich_papers_cool_detail(stub: dict) -> dict:
    paper = dict(stub)
    paper["score"] = score_paper(paper)
    return paper


def fetch_list_source(
    source: dict,
    target_date,
    days: int,
    *,
    parse_list,
    enrich_detail,
    force: bool = False,
) -> list[dict]:
    source_key = conference_source_key(source)
    state = load_conference_state()
    source_state = state.setdefault("sources", {}).setdefault(
        source_key,
        {"cursor": 0, "recommended_ids": {}, "last_runs": {}},
    )
    date_key = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    if not force and days == 1:
        cached_run = source_state.get("last_runs", {}).get(date_key)
        if isinstance(cached_run, dict) and isinstance(cached_run.get("papers"), list):
            print(
                f"  {source.get('name', 'ICML')} {source.get('year', '')}: using cached run for {date_key} "
                f"({len(cached_run['papers'])} papers)",
                file=sys.stderr,
            )
            return cached_run["papers"]

    print(f"  Fetching conference list {source.get('name')} {source.get('year')}: {source['url']}", file=sys.stderr)
    raw, _, _ = fetch_url_detailed(source["url"], timeout=45, retries=1)
    if not raw:
        return []

    stubs = parse_list(raw, source)
    cursor = int(source_state.get("cursor", 0) or 0)
    daily_take = configured_daily_take(source)
    scan_limit = configured_scan_limit(source)
    desired = max(1, daily_take * max(1, days))
    max_scan = max(1, scan_limit * max(1, days))
    scan_end = min(cursor + max_scan, len(stubs))
    print(
        f"  {source.get('name', 'ICML')} {source.get('year', '')}: {len(stubs)} posters, "
        f"cursor={cursor}, scan_end={scan_end}, max_scan={max_scan}, desired={desired}, min_score={MIN_SCORE}",
        file=sys.stderr,
    )

    recommended_ids = source_state.setdefault("recommended_ids", {})
    selected = []
    cursor_after = cursor
    for idx in range(cursor, scan_end):
        paper = enrich_detail(stubs[idx])
        cursor_after = idx + 1
        pid = paper_unique_id(paper)
        if not pid or pid in recommended_ids:
            continue
        if paper.get("score", 0) < MIN_SCORE:
            continue
        paper = enrich_selected_paper_assets(paper)
        selected.append(paper)
        if len(selected) >= desired:
            break

    source_state["cursor"] = cursor_after
    source_state.setdefault("last_runs", {})[date_key] = {
        "cursor_before": cursor,
        "cursor_after": cursor_after,
        "papers": selected,
    }
    for paper in selected:
        recommended_ids[paper_unique_id(paper)] = date_key
    write_conference_state(state)

    print(
        f"  {source.get('name', 'ICML')} {source.get('year', '')}: selected {len(selected)} papers, "
        f"cursor_after={cursor_after}",
        file=sys.stderr,
    )
    return selected


def fetch_icml_source(source: dict, target_date, days: int, *, force: bool = False) -> list[dict]:
    return fetch_list_source(
        source,
        target_date,
        days,
        parse_list=parse_icml_downloads,
        enrich_detail=enrich_icml_detail,
        force=force,
    )


def fetch_papers_cool_source(source: dict, target_date, days: int, *, force: bool = False) -> list[dict]:
    source_key = conference_source_key(source)
    state = load_conference_state()
    source_state = state.setdefault("sources", {}).setdefault(
        source_key,
        {"cursor": 0, "recommended_ids": {}, "last_runs": {}},
    )
    date_key = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    if not force and days == 1:
        cached_run = source_state.get("last_runs", {}).get(date_key)
        if isinstance(cached_run, dict) and isinstance(cached_run.get("papers"), list):
            print(
                f"  {source.get('name', 'ICLR')} {source.get('year', '')}: using cached run for {date_key} "
                f"({len(cached_run['papers'])} papers)",
                file=sys.stderr,
            )
            return cached_run["papers"]

    cursor = int(source_state.get("cursor", 0) or 0)
    daily_take = configured_daily_take(source)
    scan_limit = configured_scan_limit(source)
    desired = max(1, daily_take * max(1, days))
    max_scan = max(1, scan_limit * max(1, days))
    scan_end = cursor + max_scan
    print(
        f"  Fetching conference list {source.get('name')} {source.get('year')}: {source['url']}",
        file=sys.stderr,
    )
    print(
        f"  {source.get('name', 'ICLR')} {source.get('year', '')}: cursor={cursor}, "
        f"scan_end={scan_end}, max_scan={max_scan}, desired={desired}, min_score={MIN_SCORE}",
        file=sys.stderr,
    )

    stubs = fetch_papers_cool_stubs(source, cursor, scan_end)
    recommended_ids = source_state.setdefault("recommended_ids", {})
    selected = []
    cursor_after = cursor
    for paper in stubs:
        rank = int(paper.get("source_rank", cursor_after))
        cursor_after = rank + 1
        paper = enrich_papers_cool_detail(paper)
        pid = paper_unique_id(paper)
        if not pid or pid in recommended_ids:
            continue
        if paper.get("score", 0) < MIN_SCORE:
            continue
        paper = enrich_selected_paper_assets(paper)
        selected.append(paper)
        if len(selected) >= desired:
            break

    source_state["cursor"] = cursor_after
    source_state.setdefault("last_runs", {})[date_key] = {
        "cursor_before": cursor,
        "cursor_after": cursor_after,
        "papers": selected,
    }
    for paper in selected:
        recommended_ids[paper_unique_id(paper)] = date_key
    write_conference_state(state)

    print(
        f"  {source.get('name', 'ICLR')} {source.get('year', '')}: selected {len(selected)} papers, "
        f"cursor_after={cursor_after}",
        file=sys.stderr,
    )
    return selected


def fetch_conference_papers(target_date, days: int, *, force: bool = False) -> list[dict]:
    selected: list[dict] = []
    for source in resolve_conference_sources():
        source_type = str(source.get("type", "")).lower()
        if source_type == "icml_downloads":
            selected.extend(fetch_icml_source(source, target_date, days, force=force))
        elif source_type == "papers_cool_venue":
            selected.extend(fetch_papers_cool_source(source, target_date, days, force=force))
        else:
            print(f"  [WARN] unsupported conference source type: {source_type}", file=sys.stderr)
    return sorted(selected, key=lambda p: (p.get("conference", ""), p.get("source_rank", 10**9)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--days", type=int, default=1, help="Number of daily batches to fetch (default: 1)")
    parser.add_argument("--force", action="store_true", help="Ignore same-day cache and advance from current cursor")
    args = parser.parse_args()

    if not KEYWORDS:
        print("  [WARN] no conference keywords configured; output will be empty", file=sys.stderr)

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date
        else datetime.now().date()
    )
    days = max(1, args.days)
    print(
        f"[fetch_and_score] conference mode {target_date}, days={days}, keywords={len(KEYWORDS)}",
        file=sys.stderr,
    )

    papers = fetch_conference_papers(target_date, days, force=args.force)
    json.dump(papers, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
