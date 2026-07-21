#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_SHARED_DIR = _SKILL_DIR.parent / "_shared"
_TEMPLATE_PATH = _SKILL_DIR / "assets" / "domain-gallery-template.html"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import (  # noqa: E402
    domain_project_content_dir,
    domain_project_papers_dir,
)


TEMPLATE_FIELDS = (
    "PAGE_TITLE",
    "TITLE",
    "SUBTITLE",
    "STATS",
    "NAV",
    "ARTICLES",
    "FOOTER",
)


def main() -> int:
    args = parse_args()
    category_parts = split_category_path(args.category_path) if args.category_path else []
    category_display = " / ".join(category_parts)
    content_dir = domain_project_content_dir(args.domain)
    papers_dir = domain_project_papers_dir(args.domain)
    selected_pages = load_selected_pages(content_dir, category_parts)
    entries = collect_entries(selected_pages)
    if not entries:
        raise SystemExit("no domain paper entries found for the requested Gallery")

    output_path = resolve_output_path(
        content_dir=content_dir,
        domain=args.domain,
        category_display=category_display,
        raw_output=args.output,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = output_path.with_name(f"{output_path.stem}-assets")
    temp_assets = Path(
        tempfile.mkdtemp(prefix=f".{assets_dir.name}-", dir=output_path.parent)
    )

    try:
        rendered, copied_assets = render_gallery(
            domain=args.domain,
            category_display=category_display,
            entries=entries,
            selected_page_count=len(selected_pages),
            papers_dir=papers_dir,
            assets_dir_name=assets_dir.name,
            temp_assets=temp_assets,
            title_override=args.title,
            subtitle_override=args.subtitle,
        )
        replace_assets_dir(temp_assets, assets_dir, copied_assets)
        write_atomic(output_path, rendered)
    except Exception:
        shutil.rmtree(temp_assets, ignore_errors=True)
        raise

    print(
        json.dumps(
            {
                "domain": args.domain,
                "category_path": category_display or None,
                "source_page_count": len(selected_pages),
                "paper_count": len(entries),
                "html_path": str(output_path),
                "assets_path": str(assets_dir) if copied_assets else None,
                "copied_asset_count": copied_assets,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a domain or category Research Gallery to static HTML."
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--category-path", "--category", default="", dest="category_path")
    parser.add_argument(
        "--output",
        default="",
        help="Output HTML path. Defaults to {domain}/html/index.html or a category slug.",
    )
    parser.add_argument("--title", default="", help="Optional page title override.")
    parser.add_argument("--subtitle", default="", help="Optional page subtitle override.")
    return parser.parse_args()


def split_category_path(raw: str) -> list[str]:
    normalized = raw.replace(">", "/")
    parts = [part.strip() for part in normalized.split("/") if part.strip()]
    if not parts:
        raise SystemExit("category path cannot be empty")
    for part in parts:
        if part in {".", ".."} or "\x00" in part:
            raise SystemExit(f"invalid category path part: {part!r}")
    return parts


def load_selected_pages(
    content_dir: Path, category_parts: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    sidecar_path = content_dir / ".domain-papers.json"
    if not sidecar_path.exists():
        raise SystemExit(f"domain Gallery sidecar not found: {sidecar_path}")
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid domain Gallery sidecar: {sidecar_path}: {exc}") from exc

    pages = data.get("pages", {})
    if not isinstance(pages, dict):
        raise SystemExit(f"invalid pages object in domain Gallery sidecar: {sidecar_path}")

    if category_parts:
        requested_key = "/".join(category_parts) + ".md"
        page = pages.get(requested_key)
        if not isinstance(page, dict):
            available = ", ".join(sorted(display_category(key) for key in pages)) or "None"
            raise SystemExit(
                f"category Gallery not found: {' / '.join(category_parts)}. "
                f"Available categories: {available}"
            )
        return [(requested_key, page)]

    return [
        (key, value)
        for key, value in sorted(pages.items())
        if isinstance(key, str) and isinstance(value, dict)
    ]


def collect_entries(
    selected_pages: list[tuple[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for page_key, page_entries in selected_pages:
        category = display_category(page_key)
        for value in page_entries.values():
            if not isinstance(value, dict):
                continue
            if not value.get("title") or not value.get("note") or not value.get("year"):
                continue
            entry = dict(value)
            entry["_category"] = str(entry.get("category_path") or category)
            entries.append(entry)
    return sorted(entries, key=entry_sort_key)


def display_category(page_key: str) -> str:
    path = page_key[:-3] if page_key.endswith(".md") else page_key
    return " / ".join(part for part in path.split("/") if part)


def entry_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    try:
        year = -int(entry["year"])
    except (KeyError, TypeError, ValueError):
        year = 0
    published = str(entry.get("published_date", ""))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
        return (year, 0, -int(published.replace("-", "")), str(entry["title"]).casefold())
    return (year, 1, str(entry["title"]).casefold())


def resolve_output_path(
    *, content_dir: Path, domain: str, category_display: str, raw_output: str
) -> Path:
    if raw_output:
        output = Path(raw_output).expanduser()
        if output.suffix.lower() != ".html":
            raise SystemExit("--output must point to an .html file")
        return output
    html_dir = content_dir.parent / "html"
    filename = f"{slugify(category_display)}.html" if category_display else "index.html"
    return html_dir / filename


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    pieces: list[str] = []
    previous_dash = False
    for char in normalized:
        if char.isalnum():
            pieces.append(char)
            previous_dash = False
        elif not previous_dash:
            pieces.append("-")
            previous_dash = True
    return "".join(pieces).strip("-") or "gallery"


def render_gallery(
    *,
    domain: str,
    category_display: str,
    entries: list[dict[str, Any]],
    selected_page_count: int,
    papers_dir: Path,
    assets_dir_name: str,
    temp_assets: Path,
    title_override: str,
    subtitle_override: str,
) -> tuple[str, int]:
    domain_view = not category_display
    title = title_override or (f"{domain}: {category_display}" if category_display else domain)
    if subtitle_override:
        subtitle = subtitle_override
    elif category_display:
        subtitle = f"A curated map of papers in {category_display} within {domain}."
    else:
        subtitle = (
            f"A curated map of papers across {selected_page_count} research "
            f"subdomains in {domain}."
        )

    year_counts = Counter(int(entry["year"]) for entry in entries)
    stats = [count_label(len(entries), "paper")]
    if domain_view:
        stats.append(count_label(selected_page_count, "subdomain"))
    stats.extend(f"{year}: {year_counts[year]}" for year in sorted(year_counts, reverse=True))
    stats.append(f"Generated {date.today().isoformat()}")

    nav_items = []
    article_items = []
    copied_assets = 0
    for index, entry in enumerate(entries, start=1):
        nav_items.append(
            f'<a href="#paper-{index}">{index}. {escape(entry["note"])}</a>'
        )
        figure_html, copied = render_figure(
            entry=entry,
            index=index,
            papers_dir=papers_dir,
            assets_dir_name=assets_dir_name,
            temp_assets=temp_assets,
        )
        copied_assets += copied
        article_items.append(
            render_article(
                entry=entry,
                index=index,
                include_category=domain_view,
                figure_html=figure_html,
            )
        )

    replacements = {
        "PAGE_TITLE": escape(title),
        "TITLE": escape(title),
        "SUBTITLE": escape(subtitle),
        "STATS": "".join(f"<span>{escape(item)}</span>" for item in stats),
        "NAV": "".join(nav_items),
        "ARTICLES": "\n".join(article_items),
        "FOOTER": escape(
            f"Source: Obsidian domain paper vault, {domain}"
            + (f" / {category_display}." if category_display else ".")
        ),
    }
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    for field in TEMPLATE_FIELDS:
        token = "{{" + field + "}}"
        if token not in template:
            raise RuntimeError(f"template field missing: {token}")
        template = template.replace(token, replacements[field])
    return template, copied_assets


def render_article(
    *,
    entry: dict[str, Any],
    index: int,
    include_category: bool,
    figure_html: str,
) -> str:
    pills = [str(entry["year"]), str(entry.get("venue", "")), str(entry["note"])]
    if include_category:
        pills.append(str(entry.get("_category", "")))
    pill_html = " ".join(
        f'<span class="pill">{escape(value)}</span>' for value in pills if value
    )
    links_html = ""
    url = str(entry.get("url", "")).strip()
    link_url = safe_web_url(url)
    if link_url:
        links_html = (
            f'<a class="paper-link" href="{escape_url(link_url)}" target="_blank" '
            'rel="noopener">Link</a>'
        )

    guide_fields = (
        ("问题背景", entry.get("background", "")),
        ("核心方法", entry.get("method", "")),
        ("评估", entry.get("evaluation", "")),
        ("借鉴意义", entry.get("significance", "")),
    )
    guide_html = "".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>"
        for label, value in guide_fields
        if value
    )
    related = str(entry.get("related_work", "")).strip()
    related_html = (
        f'<div class="related"><strong>Related work:</strong> {escape(related)}</div>'
        if related
        else ""
    )
    abstract = str(entry.get("abstract_en", "")).strip()
    abstract_html = (
        f"<details><summary>Abstract</summary><p>{escape(abstract)}</p></details>"
        if abstract
        else ""
    )

    return f"""
    <article class="paper" id="paper-{index}">
      <div class="paper-topline"><span class="rank">{index}</span><div class="meta">{pill_html}</div></div>
      <h2>{escape(entry['title'])}</h2>
      <p class="summary">{escape(entry.get('summary', ''))}</p>
      {figure_html}
      <div class="links">{links_html}</div>
      <details open>
        <summary>中文导读</summary>
        <dl>{guide_html}</dl>
        {related_html}
      </details>
      {abstract_html}
    </article>""".rstrip()


def render_figure(
    *,
    entry: dict[str, Any],
    index: int,
    papers_dir: Path,
    assets_dir_name: str,
    temp_assets: Path,
) -> tuple[str, int]:
    parsed = parse_figure(str(entry.get("figure", "")))
    if not parsed:
        return "", 0
    alt, source = parsed
    parsed_url = urlparse(source)
    if parsed_url.scheme in {"http", "https"}:
        image_source = source
        copied = 0
    else:
        local_path = resolve_local_image(source, papers_dir)
        if not local_path:
            return "", 0
        target_name = f"{index:02d}-{safe_filename(local_path.name)}"
        shutil.copy2(local_path, temp_assets / target_name)
        image_source = f"{assets_dir_name}/{target_name}"
        copied = 1
    image_alt = alt or str(entry.get("title", "Figure"))
    return (
        f'<figure class="teaser"><img src="{escape_url(image_source)}" '
        f'alt="{escape(image_alt)}" loading="lazy"></figure>',
        copied,
    )


def parse_figure(markdown: str) -> tuple[str, str] | None:
    standard = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", markdown)
    if standard:
        return standard.group(1).strip(), standard.group(2).strip()
    obsidian = re.search(r"!\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", markdown)
    if obsidian:
        return "", obsidian.group(1).strip()
    return None


def resolve_local_image(source: str, papers_dir: Path) -> Path | None:
    raw_path = Path(unquote(source))
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend(
            [
                papers_dir / raw_path,
                papers_dir / "assets" / raw_path,
                papers_dir / "assets" / raw_path.name,
                papers_dir.parent / raw_path,
            ]
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def safe_filename(filename: str) -> str:
    path = Path(filename)
    stem = slugify(path.stem)
    suffix = re.sub(r"[^A-Za-z0-9.]", "", path.suffix.lower())
    return f"{stem}{suffix or '.bin'}"


def replace_assets_dir(temp_assets: Path, assets_dir: Path, copied_assets: int) -> None:
    if assets_dir.is_symlink() or assets_dir.is_file():
        assets_dir.unlink()
    elif assets_dir.exists():
        shutil.rmtree(assets_dir)
    if copied_assets:
        temp_assets.replace(assets_dir)
    else:
        shutil.rmtree(temp_assets)


def write_atomic(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def escape_url(value: str) -> str:
    return html.escape(value, quote=True)


def count_label(count: int, noun: str) -> str:
    return f"{count} {noun if count == 1 else noun + 's'}"


def safe_web_url(value: str) -> str:
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} else ""


if __name__ == "__main__":
    raise SystemExit(main())
