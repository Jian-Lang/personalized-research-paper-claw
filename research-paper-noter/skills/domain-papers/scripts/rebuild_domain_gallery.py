#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import update_domain_content as gallery  # noqa: E402
from user_config import validate_domain_name  # noqa: E402


NOTE_FIELDS = {
    "summary": "one_sentence",
    "abstract_en": "abstract_en",
    "abstract_zh": "abstract_zh",
    "background": "background",
    "method": "method",
    "evaluation": "evaluation",
    "significance": "significance",
    "figure": "figure",
}


def main() -> int:
    args = parse_args()
    domain = validate_domain(args.domain)
    requested_parts = (
        gallery.split_category_path(args.category_path) if args.category_path else []
    )
    requested_key = category_page_key(requested_parts) if requested_parts else ""

    papers_dir = gallery.domain_project_papers_dir(domain)
    content_dir = gallery.domain_project_content_dir(domain)
    if not papers_dir.is_dir():
        raise SystemExit(f"domain paper directory not found: {papers_dir}")
    content_dir.mkdir(parents=True, exist_ok=True)

    sidecar_data, old_pages = load_sidecar(content_dir)
    existing_pages = load_existing_pages(content_dir, old_pages)
    old_by_note = index_old_entries(existing_pages)
    entries_by_page = scan_current_notes(domain, papers_dir, old_by_note)

    available_keys = set(existing_pages) | set(entries_by_page)
    if requested_key and requested_key not in available_keys:
        available = ", ".join(display_category(key) for key in sorted(available_keys)) or "None"
        raise SystemExit(
            f"category Gallery not found: {' / '.join(requested_parts)}. "
            f"Available categories: {available}"
        )

    target_keys = {requested_key} if requested_key else available_keys
    if not target_keys:
        raise SystemExit(f"no domain paper notes or Gallery pages found for: {domain}")

    rendered_pages: dict[str, str] = {}
    refreshed_entries: dict[str, dict[str, dict[str, Any]]] = {}
    for key in sorted(target_keys):
        category_parts = page_key_parts(key)
        content_path = gallery.content_page_path(content_dir, category_parts)
        previous = content_path.read_text(encoding="utf-8") if content_path.exists() else ""
        entries = entries_by_page.get(key, {})
        rendered = gallery.render_content_page(
            previous=previous,
            domain=domain,
            category_parts=category_parts,
            entries=entries.values(),
        )
        rendered_pages[key] = refresh_updated_frontmatter(rendered)
        refreshed_entries[key] = entries

    for key, rendered in rendered_pages.items():
        path = gallery.content_page_path(content_dir, page_key_parts(key))
        path.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(path, rendered)

    pages = dict(old_pages) if requested_key else {}
    pages.update(refreshed_entries)
    sidecar_data["pages"] = pages
    sidecar = gallery.sidecar_path(content_dir)
    write_atomic(
        sidecar,
        json.dumps(sidecar_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    index_path = gallery.update_domain_index(domain, content_dir)

    paper_count = sum(len(entries) for entries in refreshed_entries.values())
    print(
        json.dumps(
            {
                "domain": domain,
                "category_path": " / ".join(requested_parts) or None,
                "content_pages": [
                    str(gallery.content_page_path(content_dir, page_key_parts(key)))
                    for key in sorted(target_keys)
                ],
                "paper_count": paper_count,
                "index_path": str(index_path),
                "sidecar_path": str(sidecar),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild every category Markdown Gallery in a domain, or one selected category, "
            "from current paper notes."
        )
    )
    parser.add_argument("--domain", required=True)
    parser.add_argument("--category-path", "--category", default="", dest="category_path")
    return parser.parse_args()


def validate_domain(raw: str) -> str:
    try:
        return validate_domain_name(raw)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def load_sidecar(content_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    path = gallery.sidecar_path(content_dir)
    if not path.exists():
        return {"pages": {}}, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid domain Gallery sidecar: {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("pages", {}), dict):
        raise SystemExit(f"invalid pages object in domain Gallery sidecar: {path}")
    pages = {
        key: value
        for key, value in data.get("pages", {}).items()
        if isinstance(key, str) and isinstance(value, dict)
    }
    for key in pages:
        page_key_parts(key)
    return data, pages


def load_existing_pages(
    content_dir: Path, sidecar_pages: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    pages: dict[str, dict[str, dict[str, Any]]] = {}
    keys = set(sidecar_pages)
    keys.update(
        path.relative_to(content_dir).as_posix()
        for path in content_dir.rglob("*.md")
        if path.name != "_index.md"
        and not any(part.startswith(".") for part in path.relative_to(content_dir).parts)
    )
    for key in sorted(keys):
        parts = page_key_parts(key)
        path = gallery.content_page_path(content_dir, parts)
        previous = path.read_text(encoding="utf-8") if path.exists() else ""
        raw_entries = gallery.read_entries(content_dir, path, previous)
        pages[key] = {
            entry_key: dict(entry)
            for entry_key, entry in raw_entries.items()
            if isinstance(entry, dict)
        }
    return pages


def index_old_entries(
    pages: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for page_key, entries in pages.items():
        category = display_category(page_key)
        for entry in entries.values():
            note = str(entry.get("note", "")).strip()
            if not note:
                continue
            preserved = dict(entry)
            preserved.setdefault("category_path", category)
            indexed[note_identity(note)] = preserved
    return indexed


def scan_current_notes(
    domain: str, papers_dir: Path, old_by_note: dict[str, dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    errors: list[str] = []
    note_paths = sorted(papers_dir.glob("*.md"), key=lambda path: path.name.casefold())
    if not note_paths:
        raise SystemExit(f"no Markdown paper notes found in: {papers_dir}")

    for note_path in note_paths:
        content = note_path.read_text(encoding="utf-8")
        old = old_by_note.get(note_identity(note_path.stem), {})
        category_raw = first_nonempty(
            gallery.extract_frontmatter_value(content, "category_path"),
            gallery.extract_frontmatter_value(content, "category"),
            gallery.extract_frontmatter_value(content, "zotero_collection"),
            str(old.get("category_path", "")),
        )
        if not category_raw:
            errors.append(f"{note_path.name}: missing category/category_path/zotero_collection")
            continue
        try:
            category_parts = gallery.split_category_path(category_raw)
        except SystemExit as exc:
            errors.append(f"{note_path.name}: {exc}")
            continue

        year_raw = first_nonempty(
            gallery.extract_frontmatter_value(content, "year"), str(old.get("year", ""))
        )
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            errors.append(f"{note_path.name}: missing or invalid year")
            continue

        title = first_nonempty(
            gallery.extract_frontmatter_value(content, "title"),
            str(old.get("title", "")),
            note_path.stem,
        )
        venue = first_nonempty(
            gallery.extract_frontmatter_value(content, "venue"), str(old.get("venue", ""))
        )
        category = " / ".join(category_parts)
        note_extract = gallery.load_note_extract(
            domain,
            {"note": note_path.stem},
        )
        entry = dict(old)
        entry.update(
            {
                "title": title,
                "note": note_path.stem,
                "year": year,
                "venue": venue,
                "domain": domain,
                "category_path": category,
                "updated": first_nonempty(
                    str(old.get("updated", "")),
                    gallery.extract_frontmatter_value(content, "created"),
                    date.today().isoformat(),
                ),
                "published_date": first_nonempty(
                    gallery.extract_frontmatter_value(content, "published_date"),
                    str(old.get("published_date", "")),
                ),
                "url": first_nonempty(
                    gallery.extract_link(content, "Paper"),
                    gallery.extract_link(content, "arXiv"),
                    str(old.get("url", "")),
                ),
            }
        )
        # Existing Gallery prose was curated when the paper was added. Rebuild structure and
        # metadata from notes without replacing that prose with raw section excerpts.
        for entry_field, note_field in NOTE_FIELDS.items():
            entry[entry_field] = first_nonempty(
                str(old.get(entry_field, "")), note_extract.get(note_field, "")
            )
        entry = gallery.normalize_entry(entry)

        page = category_page_key(category_parts)
        key = gallery.entry_key(entry)
        if key in grouped[page]:
            errors.append(f"{note_path.name}: duplicate paper title in {category}")
            continue
        grouped[page][key] = entry

    if errors:
        raise SystemExit("cannot rebuild Gallery:\n- " + "\n- ".join(errors))
    return dict(grouped)


def first_nonempty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def note_identity(value: str) -> str:
    return gallery.strip_md_suffix(value).casefold()


def category_page_key(parts: list[str]) -> str:
    return "/".join(parts) + ".md"


def page_key_parts(key: str) -> list[str]:
    if not key.endswith(".md"):
        raise SystemExit(f"invalid Gallery page key: {key}")
    parts = gallery.split_category_path(key[:-3])
    if category_page_key(parts) != key:
        raise SystemExit(f"invalid Gallery page key: {key}")
    return parts


def display_category(key: str) -> str:
    return " / ".join(page_key_parts(key))


def refresh_updated_frontmatter(content: str) -> str:
    if not content.startswith("---\n"):
        return content
    end = content.find("\n---", 4)
    if end == -1:
        return content
    frontmatter = content[:end]
    today = date.today().isoformat()
    if re.search(r"^updated:\s*.*$", frontmatter, flags=re.MULTILINE):
        refreshed = re.sub(
            r"^updated:\s*.*$", f"updated: {today}", frontmatter, count=1, flags=re.MULTILINE
        )
    else:
        refreshed = frontmatter + f"\nupdated: {today}"
    return refreshed + content[end:]


def write_atomic(path: Path, content: str) -> None:
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
