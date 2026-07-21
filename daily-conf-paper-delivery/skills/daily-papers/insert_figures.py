#!/usr/bin/env python3
"""Insert available representative figures into a daily recommendation page."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def section_title(section: str) -> str:
    match = re.search(r"^###\s+\d+\.\s+(.+?)\s*$", section, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def has_image_before_abstract(section: str) -> bool:
    abstract_pos = section.find("- **论文摘要 / English**")
    prefix = section if abstract_pos < 0 else section[:abstract_pos]
    return bool(re.search(r"!\[[^\]]*\]\([^)]+\)|!\[\[[^\]]+\]\]", prefix))


def insert_figure(section: str, figure_url: str) -> str:
    if has_image_before_abstract(section):
        return section
    source_match = re.search(r"^- \*\*来源\*\*: .+?\n", section, flags=re.MULTILINE)
    insert_at = source_match.end() if source_match else len(section_title(section))
    return section[:insert_at] + f"\n![]({figure_url})\n" + section[insert_at:]


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: insert_figures.py <daily_md> <enriched_json>", file=sys.stderr)
        return 2

    daily_path = Path(sys.argv[1])
    enriched_path = Path(sys.argv[2])
    if not daily_path.exists() or not enriched_path.exists():
        print("daily markdown or enriched json missing", file=sys.stderr)
        return 1

    papers = json.loads(enriched_path.read_text(encoding="utf-8"))
    figures = {
        normalize_title(paper.get("title", "")): paper.get("figure_url", "")
        for paper in papers
        if isinstance(paper, dict) and paper.get("title") and paper.get("figure_url")
    }
    if not figures:
        print("No figure_url entries found.")
        return 0

    text = daily_path.read_text(encoding="utf-8")
    parts = re.split(r"(?=^###\s+\d+\.\s+)", text, flags=re.MULTILINE)
    changed = 0
    for idx, part in enumerate(parts):
        title = section_title(part)
        if not title:
            continue
        figure_url = figures.get(normalize_title(title))
        if not figure_url:
            continue
        updated = insert_figure(part, figure_url)
        if updated != part:
            parts[idx] = updated
            changed += 1

    if changed:
        daily_path.write_text("".join(parts), encoding="utf-8")
    print(f"Inserted {changed} figure(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
