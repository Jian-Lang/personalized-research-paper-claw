#!/usr/bin/env python3
"""
fetch_and_score.py - conference paper fetcher for daily recommendations.

The active recommender reads repository-local accepted-paper JSONL snapshots,
scores title + abstract against the user's preferences, and emits the next
unrecommended papers for each configured conference.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent.parent / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import daily_papers_config, daily_project_dir


def normalize_match_text(value: str) -> str:
    """Normalize punctuation while preserving whole word/phrase boundaries."""
    value = html.unescape(str(value or "")).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def unique_terms(values) -> list[str]:
    terms: dict[str, str] = {}
    for value in values or []:
        display = re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip(" \t\r\n:;,")
        normalized = normalize_match_text(display)
        if normalized and normalized not in terms:
            terms[normalized] = display
    return list(terms.values())


def contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = normalize_match_text(term)
    return bool(normalized_term) and f" {normalized_term} " in f" {normalized_text} "


CONFIG = daily_papers_config()
TOPICS = unique_terms(CONFIG.get("topics", []))
KEYWORDS = unique_terms(CONFIG.get("keywords", []))
EXCLUDE_KEYWORDS = unique_terms(CONFIG.get("exclude_keywords", []))
MIN_SCORE = int(CONFIG.get("min_score", 2))
PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFERENCE_STATE_PATH = PROJECT_DIR / "state" / "conference-state.json"
LEGACY_CONFERENCE_STATE_PATH = daily_project_dir() / ".conference-state.json"
DEFAULT_DAILY_TAKE = 5
DEFAULT_SCAN_LIMIT = 1000
PAPERLIST_DATA_DIR = PROJECT_DIR / "data" / "paperlist"


def configured_daily_take(source: dict) -> int:
    return int(source.get("daily_take") or CONFIG.get("daily_take") or DEFAULT_DAILY_TAKE)


def configured_scan_limit(source: dict) -> int:
    return int(source.get("scan_window") or CONFIG.get("scan_limit") or DEFAULT_SCAN_LIMIT)


def clean_text(text: str) -> str:
    text = html.unescape(str(text or ""))
    return re.sub(r"\s+", " ", text).strip(" \t\r\n:;,")


def normalize_title_key(text: str) -> str:
    text = clean_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", clean_text(text).lower()).strip("-")


def paperlist_relative_path(conference: str, year: int) -> Path:
    return Path(conference.upper()) / f"{conference.lower()}_{year}.jsonl"


def read_paperlist_jsonl(source: dict) -> str:
    rel_path = paperlist_relative_path(str(source["name"]), int(source["year"]))
    snapshot_path = PAPERLIST_DATA_DIR / rel_path
    if snapshot_path.exists():
        return snapshot_path.read_text(encoding="utf-8")

    print(
        f"  [WARN] missing local paperlist snapshot: {snapshot_path}. "
        "Add a compatible JSONL file or import one with scripts/sync_paperlist.py --source-dir.",
        file=sys.stderr,
    )
    return ""


def score_paper(paper: dict) -> int:
    title = normalize_match_text(paper.get("title", ""))
    abstract = normalize_match_text(paper.get("abstract", ""))
    excluded_by = [
        term for term in EXCLUDE_KEYWORDS if contains_term(title, term) or contains_term(abstract, term)
    ]
    matched_topics = [term for term in TOPICS if contains_term(title, term) or contains_term(abstract, term)]
    title_keywords = [term for term in KEYWORDS if contains_term(title, term)]
    abstract_keywords = [
        term for term in KEYWORDS if term not in title_keywords and contains_term(abstract, term)
    ]

    score = -100 if excluded_by else len(matched_topics) + 3 * len(title_keywords) + len(abstract_keywords)
    paper["score_breakdown"] = {
        "topics": matched_topics,
        "title_keywords": title_keywords,
        "abstract_keywords": abstract_keywords,
        "excluded_by": excluded_by,
    }
    return score


def paper_unique_id(paper: dict) -> str:
    if paper.get("source_id"):
        return str(paper["source_id"])
    title_slug = slugify(paper.get("title", ""))
    return title_slug[:140]


def resolve_conference_sources() -> list[dict]:
    configured = CONFIG.get("conferences")
    if configured is None:
        configured = [CONFIG.get("conference", {})]
    elif isinstance(configured, dict):
        configured = [configured]

    sources = []
    for conference in configured:
        if not isinstance(conference, dict) or not conference.get("enabled", True):
            continue
        name = str(conference.get("name", "")).strip().upper()
        year = int(conference.get("year", 0) or 0)
        if not name or not year:
            print(f"  [WARN] invalid conference config: {conference}", file=sys.stderr)
            continue

        source = {"name": name, "type": "paperlist_jsonl"}
        source.update(conference)
        source["name"] = name
        source["year"] = year
        source["snapshot_path"] = str(paperlist_relative_path(name, year))
        source["enabled"] = True
        sources.append(source)
    return sources


def conference_source_key(source: dict) -> str:
    name = str(source.get("name", "")).strip().lower()
    year = str(source.get("year", "")).strip()
    source_type = str(source.get("type", "paperlist_jsonl")).strip().lower()
    return "-".join(part for part in (source_type, name, year) if part)


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


def source_state_title_keys(source_state: dict) -> set[str]:
    title_keys = set(source_state.get("recommended_title_keys", {}).keys())
    for run in source_state.get("last_runs", {}).values():
        if not isinstance(run, dict):
            continue
        for paper in run.get("papers", []):
            if isinstance(paper, dict):
                title_key = normalize_title_key(paper.get("title", ""))
                if title_key:
                    title_keys.add(title_key)
    return title_keys


def global_recommended_title_keys(state: dict) -> set[str]:
    title_keys: set[str] = set()
    for source_state in state.get("sources", {}).values():
        if isinstance(source_state, dict):
            title_keys.update(source_state_title_keys(source_state))
    return title_keys


def make_paper(source: dict, row: dict, rank: int) -> dict:
    conference = str(source.get("name", "")).strip().upper()
    year = int(source.get("year", 0) or 0)
    title = clean_text(row.get("title", ""))
    authors = clean_text(row.get("author", ""))
    abstract = clean_text(row.get("abstract", ""))
    site = clean_text(row.get("site", ""))
    pdf = clean_text(row.get("pdf", ""))
    status = clean_text(row.get("status", ""))
    title_slug = slugify(title) or f"paper-{rank + 1}"
    source_slug = slugify(conference) or "conference"
    return {
        "title": title,
        "authors": authors.replace("; ", ", "),
        "affiliations": "",
        "abstract": abstract,
        "url": site,
        "pdf": pdf,
        "paper_url": site,
        "date": "",
        "score": 0,
        "status": status,
        "source": f"conference-{source_slug}",
        "source_id": f"{source_slug}-{year}-{title_slug[:120]}",
        "source_rank": rank,
        "source_rank_display": rank + 1,
        "conference": conference,
        "venue": f"{conference} {year}" if year else conference,
        "year": year,
        "poster_id": title_slug[:120],
        "has_paper": bool(site or pdf),
        "figure_url": "",
        "section_headers": [],
        "captions": [],
        "has_real_world": False,
        "method_names": [],
        "method_summary": "",
        "score_breakdown": {},
        "source_kind": "paperlist_jsonl",
    }


def parse_paperlist_jsonl(raw: str, source: dict) -> list[dict]:
    papers: list[dict] = []
    for line_no, line in enumerate(raw.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"  [WARN] invalid JSONL line {line_no}: {e}", file=sys.stderr)
            continue
        paper = make_paper(source, row, len(papers))
        if paper["title"]:
            papers.append(paper)
    return papers


def fetch_paperlist_source(source: dict, target_date, days: int, *, force: bool = False) -> list[dict]:
    source_key = conference_source_key(source)
    state = load_conference_state()
    source_state = state.setdefault("sources", {}).setdefault(
        source_key,
        {"cursor": 0, "recommended_ids": {}, "recommended_title_keys": {}, "last_runs": {}},
    )
    source_state.setdefault("recommended_ids", {})
    source_state.setdefault("recommended_title_keys", {})
    source_state.setdefault("last_runs", {})

    date_key = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    if not force and days == 1:
        cached_run = source_state.get("last_runs", {}).get(date_key)
        if isinstance(cached_run, dict) and isinstance(cached_run.get("papers"), list):
            print(
                f"  {source.get('name')} {source.get('year')}: using cached run for {date_key} "
                f"({len(cached_run['papers'])} papers)",
                file=sys.stderr,
            )
            return cached_run["papers"]

    print(
        f"  Reading accepted paper list {source.get('name')} {source.get('year')}: "
        f"data/paperlist/{source.get('snapshot_path')}",
        file=sys.stderr,
    )
    raw = read_paperlist_jsonl(source)
    if not raw:
        return []
    papers = parse_paperlist_jsonl(raw, source)

    cursor = int(source_state.get("cursor", 0) or 0)
    daily_take = configured_daily_take(source)
    scan_limit = configured_scan_limit(source)
    desired = max(1, daily_take * max(1, days))
    max_scan = max(1, scan_limit * max(1, days))
    scan_end = min(cursor + max_scan, len(papers))
    recommended_ids = source_state["recommended_ids"]
    recommended_title_keys = source_state["recommended_title_keys"]
    all_recommended_title_keys = global_recommended_title_keys(state)

    print(
        f"  {source.get('name')} {source.get('year')}: {len(papers)} accepted papers, "
        f"cursor={cursor}, scan_end={scan_end}, max_scan={max_scan}, desired={desired}, min_score={MIN_SCORE}",
        file=sys.stderr,
    )

    selected = []
    cursor_after = cursor
    for idx in range(cursor, scan_end):
        paper = papers[idx]
        cursor_after = idx + 1
        paper["score"] = score_paper(paper)
        pid = paper_unique_id(paper)
        title_key = normalize_title_key(paper.get("title", ""))
        if not pid or pid in recommended_ids:
            continue
        if title_key and title_key in all_recommended_title_keys:
            continue
        if paper.get("score", 0) < MIN_SCORE:
            continue
        selected.append(paper)
        if len(selected) >= desired:
            break

    source_state["cursor"] = cursor_after
    source_state["last_runs"][date_key] = {
        "cursor_before": cursor,
        "cursor_after": cursor_after,
        "papers": selected,
    }
    for paper in selected:
        pid = paper_unique_id(paper)
        title_key = normalize_title_key(paper.get("title", ""))
        recommended_ids[pid] = date_key
        if title_key:
            recommended_title_keys[title_key] = date_key
    write_conference_state(state)

    print(
        f"  {source.get('name')} {source.get('year')}: selected {len(selected)} papers, "
        f"cursor_after={cursor_after}",
        file=sys.stderr,
    )
    return selected


def fetch_conference_papers(target_date, days: int, *, force: bool = False) -> list[dict]:
    selected: list[dict] = []
    for source in resolve_conference_sources():
        source_type = str(source.get("type", "")).lower()
        if source_type == "paperlist_jsonl":
            selected.extend(fetch_paperlist_source(source, target_date, days, force=force))
        else:
            print(f"  [WARN] unsupported conference source type: {source_type}", file=sys.stderr)
    return sorted(selected, key=lambda p: (p.get("conference", ""), p.get("source_rank", 10**9)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of daily recommendation quotas to fetch (default: 1)",
    )
    parser.add_argument("--force", action="store_true", help="Ignore same-day cache and advance from current cursor")
    args = parser.parse_args()

    if not TOPICS and not KEYWORDS:
        print("  [WARN] no topics or keywords configured; output will be empty", file=sys.stderr)

    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now().date()
    days = max(1, args.days)
    print(
        f"[fetch_and_score] paperlist mode {target_date}, days={days}, "
        f"topics={len(TOPICS)}, keywords={len(KEYWORDS)}",
        file=sys.stderr,
    )

    papers = fetch_conference_papers(target_date, days, force=args.force)
    json.dump(papers, sys.stdout, ensure_ascii=False, indent=2)
    print(file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
