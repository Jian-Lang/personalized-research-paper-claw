#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen
import xml.etree.ElementTree as ET


_SCRIPT_DIR = Path(__file__).resolve().parent
_SHARED_DIR = _SCRIPT_DIR.parents[1] / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import (
    domain_project_content_dir,
    domain_project_papers_dir,
    domain_vault_path,
    markdown_root_path,
)


START_MARKER = "<!-- domain-papers:start -->"
END_MARKER = "<!-- domain-papers:end -->"
ENTRY_PREFIX = "<!-- domain-paper:"
ENTRY_RE = re.compile(r"<!--\s*domain-paper:\s*(\{.*?\})\s*-->")


def main() -> int:
    args = parse_args()
    category_parts = split_category_path(args.category_path)
    entry = normalize_entry(
        {
            "title": args.title,
            "note": strip_md_suffix(args.note),
            "year": int(args.year),
            "url": args.url or "",
            "venue": args.venue or "",
            "summary": args.summary or "",
            "abstract_en": args.abstract_en or "",
            "abstract_zh": args.abstract_zh or "",
            "background": args.background or "",
            "method": args.method or "",
            "evaluation": args.evaluation or "",
            "significance": args.significance or "",
            "related_work": args.related_work or "",
            "figure": args.figure or "",
            "published_date": args.published_date or "",
            "domain": args.domain,
            "category_path": " / ".join(category_parts),
            "updated": date.today().isoformat(),
        }
    )

    papers_dir = domain_project_papers_dir(args.domain)
    content_dir = domain_project_content_dir(args.domain)
    papers_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)

    content_path = content_page_path(content_dir, category_parts)
    content_path.parent.mkdir(parents=True, exist_ok=True)
    previous = content_path.read_text(encoding="utf-8") if content_path.exists() else ""
    entries = read_entries(content_dir, content_path, previous)
    entries[entry_key(entry)] = entry
    enrich_entries_for_sorting(entries)
    write_entries(content_dir, content_path, entries)
    rendered = render_content_page(
        previous=previous,
        domain=args.domain,
        category_parts=category_parts,
        entries=entries.values(),
    )
    content_path.write_text(rendered, encoding="utf-8")

    index_path = update_domain_index(args.domain, content_dir)
    print(
        json.dumps(
            {
                "domain_vault": str(domain_vault_path()),
                "papers_dir": str(papers_dir),
                "content_path": str(content_path),
                "index_path": str(index_path),
                "entry_count": len(entries),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update a domain paper content page.")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--category-path", "--category", required=True, dest="category_path")
    parser.add_argument("--title", required=True)
    parser.add_argument("--note", required=True)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--url", default="")
    parser.add_argument("--venue", default="")
    parser.add_argument("--published-date", default="", dest="published_date")
    parser.add_argument("--summary", default="")
    parser.add_argument("--abstract-en", default="")
    parser.add_argument("--abstract-zh", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--evaluation", default="")
    parser.add_argument("--significance", default="")
    parser.add_argument("--related-work", default="", dest="related_work")
    parser.add_argument("--figure", default="")
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


def content_page_path(content_dir: Path, category_parts: list[str]) -> Path:
    if len(category_parts) == 1:
        return content_dir / f"{category_parts[0]}.md"
    return content_dir.joinpath(*category_parts[:-1]) / f"{category_parts[-1]}.md"


def strip_md_suffix(note: str) -> str:
    path = Path(note.strip())
    return path.stem if path.suffix == ".md" else note.strip()


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in entry.items():
        if isinstance(value, str):
            normalized[key] = " ".join(value.split())
        else:
            normalized[key] = value
    return normalized


def entry_key(entry: dict[str, Any]) -> str:
    return re.sub(r"\s+", " ", entry["title"].casefold()).strip()


def read_entries(content_dir: Path, content_path: Path, content: str) -> dict[str, dict[str, Any]]:
    entries = read_sidecar_entries(content_dir, content_path)
    if entries:
        return entries

    # Migration path for old content files that embedded metadata comments.
    entries: dict[str, dict[str, Any]] = {}
    for match in ENTRY_RE.finditer(content):
        try:
            entry = normalize_entry(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
        if "title" in entry and "year" in entry and "note" in entry:
            entries[entry_key(entry)] = entry
    return entries


def sidecar_path(content_dir: Path) -> Path:
    return content_dir / ".domain-papers.json"


def page_key(content_dir: Path, content_path: Path) -> str:
    return content_path.relative_to(content_dir).as_posix()


def read_sidecar_entries(content_dir: Path, content_path: Path) -> dict[str, dict[str, Any]]:
    path = sidecar_path(content_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    page_entries = data.get("pages", {}).get(page_key(content_dir, content_path), {})
    if not isinstance(page_entries, dict):
        return {}
    return {
        key: normalize_entry(value)
        for key, value in page_entries.items()
        if isinstance(value, dict) and "title" in value and "year" in value and "note" in value
    }


def write_entries(content_dir: Path, content_path: Path, entries: dict[str, dict[str, Any]]) -> None:
    path = sidecar_path(content_dir)
    data: dict[str, Any] = {"pages": {}}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {"pages": {}}
    data.setdefault("pages", {})[page_key(content_dir, content_path)] = entries
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_content_page(
    *,
    previous: str,
    domain: str,
    category_parts: list[str],
    entries: Any,
) -> str:
    managed_block = render_managed_block(domain, entries)
    if previous.count("## Papers") > 1:
        before = previous.split("## Papers", 1)[0] + "## Papers\n\n"
        return before.rstrip() + "\n\n" + managed_block + "\n"

    if START_MARKER in previous and END_MARKER in previous:
        start_index = previous.index(START_MARKER)
        end_index = previous.rindex(END_MARKER) + len(END_MARKER)
        before = previous[:start_index]
        after = previous[end_index:]
        return before.rstrip() + "\n\n" + managed_block + after

    if previous.strip():
        return previous.rstrip() + "\n\n## Papers\n\n" + managed_block + "\n"

    category_display = " / ".join(category_parts)
    return "\n".join(
        [
            "---",
            f'domain: "{escape_yaml(domain)}"',
            f'category: "{escape_yaml(category_display)}"',
            "tags: [domain-papers, content]",
            f"updated: {date.today().isoformat()}",
            "---",
            "",
            f"# {category_parts[-1]}",
            "",
            "## Papers",
            "",
            managed_block,
            "",
        ]
    )


def render_managed_block(domain: str, entries: Any) -> str:
    sorted_entries = sorted(entries, key=entry_sort_key)
    lines = [START_MARKER]
    current_year: int | None = None
    for index, entry in enumerate(sorted_entries, start=1):
        year = int(entry["year"])
        if year != current_year:
            if current_year is not None:
                lines.append("")
            lines.extend([f"### {year}", ""])
            current_year = year
        lines.extend(render_entry_block(domain, entry, index))
    if not sorted_entries:
        lines.append("- 暂无论文")
    lines.append(END_MARKER)
    return "\n".join(lines)


def render_entry_block(domain: str, entry: dict[str, Any], index: int) -> list[str]:
    note = load_note_extract(domain, entry)
    rendered = {**note, **manual_fields(entry)}
    links = render_links(entry, note)
    note_link = vault_wikilink(domain_project_papers_dir(domain) / entry["note"])
    lines = [
        f"#### {index}. {entry['title']}",
        f"- **加入日期**: {entry.get('updated') or date.today().isoformat()}",
        f"- **笔记**: [[{note_link}|{entry['note']}]]",
        f"- **年份**: {rendered.get('year') or entry.get('year') or '待补充'}",
        f"- **Venue**: {rendered.get('venue') or entry.get('venue') or '待补充'}",
    ]
    if links:
        lines.append(f"- **链接**: {links}")
    if rendered.get("figure"):
        lines.append(rendered["figure"])
    lines.extend(
        [
            f"- **一句话总结**: {rendered.get('one_sentence') or entry.get('summary') or '待补充'}",
            f"- **论文摘要 / English**: {rendered.get('abstract_en') or '待补充'}",
            f"- **论文摘要 / 中文**: {rendered.get('abstract_zh') or '待补充'}",
            f"- **问题背景**: {rendered.get('background') or '待补充'}",
            f"- **核心方法**: {rendered.get('method') or entry.get('summary') or '待补充'}",
            f"- **评估**: {rendered.get('evaluation') or '待补充'}",
            f"- **借鉴意义**: {rendered.get('significance') or '待补充'}",
        ]
    )
    if rendered.get("related_work"):
        lines.append(f"> **与其他工作的关系**：{rendered['related_work']}")
    lines.append("")
    return lines


def entry_sort_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    year = -int(entry["year"])
    published_date = normalize_iso_date(str(entry.get("published_date", "")))
    title = entry["title"].casefold()
    if published_date:
        # Same-year arXiv papers sort by exact publish date descending.
        return (year, 0, -iso_date_to_int(published_date), title)
    return (year, 1, title)


def normalize_iso_date(value: str) -> str:
    raw = value.strip()
    return raw if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else ""


def iso_date_to_int(value: str) -> int:
    return int(value.replace("-", ""))


def enrich_entries_for_sorting(entries: dict[str, dict[str, Any]]) -> None:
    for entry in entries.values():
        if normalize_iso_date(str(entry.get("published_date", ""))):
            continue
        if not is_arxiv_url(str(entry.get("url", ""))):
            continue
        published_date = fetch_arxiv_published_date(str(entry["url"]))
        if published_date:
            entry["published_date"] = published_date


def is_arxiv_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("arxiv.org") and "/abs/" in parsed.path


def fetch_arxiv_published_date(url: str) -> str:
    arxiv_id = extract_arxiv_id(url)
    if not arxiv_id:
        return ""
    api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        with urlopen(api_url, timeout=20) as response:
            payload = response.read()
    except (URLError, TimeoutError, OSError):
        return ""
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return ""
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = root.find("a:entry", ns)
    if entry is None:
        return ""
    published = entry.findtext("a:published", default="", namespaces=ns).strip()
    return published[:10] if normalize_iso_date(published[:10]) else ""


def extract_arxiv_id(url: str) -> str:
    match = re.search(r"arxiv\.org/abs/([^/?#]+)", url)
    if not match:
        return ""
    return re.sub(r"v\d+$", "", match.group(1).strip())


def manual_fields(entry: dict[str, Any]) -> dict[str, str]:
    fields = {
        "one_sentence": entry.get("summary", ""),
        "abstract_en": entry.get("abstract_en", ""),
        "abstract_zh": entry.get("abstract_zh", ""),
        "background": entry.get("background", ""),
        "method": entry.get("method", ""),
        "evaluation": entry.get("evaluation", ""),
        "significance": entry.get("significance", ""),
        "related_work": entry.get("related_work", ""),
        "figure": entry.get("figure", ""),
        "year": str(entry.get("year", "")),
        "venue": entry.get("venue", ""),
    }
    return {key: value for key, value in fields.items() if isinstance(value, str) and value.strip()}


def render_links(entry: dict[str, Any], note: dict[str, str]) -> str:
    links = []
    if entry.get("url"):
        links.append(f"[arXiv]({entry['url']})")
    if note.get("pdf_url"):
        links.append(f"[PDF]({note['pdf_url']})")
    if note.get("html_url"):
        links.append(f"[HTML]({note['html_url']})")
    if note.get("code_url"):
        links.append(f"[Code]({note['code_url']})")
    return " / ".join(dict.fromkeys(links))


def load_note_extract(domain: str, entry: dict[str, Any]) -> dict[str, str]:
    note_path = domain_project_papers_dir(domain) / f"{entry['note']}.md"
    if not note_path.exists():
        return {}
    content = note_path.read_text(encoding="utf-8")
    return {
        "year": extract_frontmatter_value(content, "year"),
        "venue": extract_frontmatter_value(content, "venue"),
        "one_sentence": extract_one_sentence(content),
        "abstract_en": extract_label_value(content, "论文摘要 / English"),
        "abstract_zh": extract_label_value(content, "论文摘要 / 中文"),
        "background": clean_excerpt(extract_section(content, "问题背景"), 500),
        "method": clean_excerpt(extract_section(content, "方法详解"), 700),
        "evaluation": clean_excerpt(extract_subsection(content, "实验", "主要结果"), 450)
        or clean_excerpt(extract_section(content, "实验"), 450),
        "significance": clean_excerpt(extract_subsection(content, "批判性思考", "优点"), 450),
        "figure": extract_first_image(content),
        "pdf_url": extract_link(content, "PDF"),
        "html_url": extract_link(content, "HTML"),
        "code_url": extract_link(content, "Code"),
    }


def extract_one_sentence(content: str) -> str:
    text = extract_section(content, "一句话总结")
    text = re.sub(r"^>\s*", "", text.strip(), flags=re.MULTILINE)
    return clean_excerpt(text, 260)


def extract_label_value(content: str, label: str) -> str:
    pattern = re.compile(rf"- \*\*{re.escape(label)}\*\*:\s*(.+)")
    match = pattern.search(content)
    return clean_excerpt(match.group(1), 900) if match else ""


def extract_section(content: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        return ""
    next_match = re.search(r"^## ", content[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(content)
    return content[match.end() : end].strip()


def extract_subsection(content: str, section_heading: str, subsection_heading: str) -> str:
    section = extract_section(content, section_heading)
    if not section:
        return ""
    pattern = re.compile(rf"^### {re.escape(subsection_heading)}\s*$", re.MULTILINE)
    match = pattern.search(section)
    if not match:
        return ""
    next_match = re.search(r"^### ", section[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(section)
    return section[match.end() : end].strip()


def extract_first_image(content: str) -> str:
    match = re.search(r"!\[[^\]]*\]\([^)]+\)", content)
    return match.group(0) if match else ""


def extract_link(content: str, label: str) -> str:
    match = re.search(rf"\[{re.escape(label)}\]\(([^)]+)\)", content)
    return match.group(1) if match else ""


def extract_frontmatter_value(content: str, key: str) -> str:
    if not content.startswith("---"):
        return ""
    end = content.find("\n---", 3)
    if end == -1:
        return ""
    frontmatter = content[3:end]
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", frontmatter, flags=re.MULTILINE)
    if not match:
        return ""
    return match.group(1).strip().strip('"').strip("'")


def clean_excerpt(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\$\$.*?\$\$", "", text, flags=re.DOTALL)
    text = re.sub(r"^#{3,}\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{2,}", "\n", text)
    text = " ".join(line.strip() for line in text.splitlines() if line.strip())
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def render_entry_line(domain: str, entry: dict[str, Any]) -> str:
    link = vault_wikilink(domain_project_papers_dir(domain) / entry["note"])
    chunks = [f"[[{link}|{entry['title']}]]", str(entry["year"])]
    if entry.get("venue"):
        chunks.append(entry["venue"])
    if entry.get("url"):
        chunks.append(f"[link]({entry['url']})")
    if entry.get("summary"):
        chunks.append(entry["summary"])
    return " · ".join(chunks)


def update_domain_index(domain: str, content_dir: Path) -> Path:
    index_path = content_dir / "_index.md"
    page_paths = sorted(
        path
        for path in content_dir.rglob("*.md")
        if path.name != "_index.md" and not any(part.startswith(".") for part in path.relative_to(content_dir).parts)
    )
    lines = [
        "---",
        "tags: [domain-papers, index]",
        f"updated: {date.today().isoformat()}",
        "---",
        "",
        f"# {domain}",
        "",
        "## Content",
        "",
    ]
    if page_paths:
        for path in page_paths:
            rel = path.relative_to(content_dir).with_suffix("").as_posix()
            display = rel.replace("/", " / ")
            lines.append(f"- [[{vault_wikilink(path)}|{display}]]")
    else:
        lines.append("- 暂无内容")
    lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def vault_wikilink(path: Path) -> str:
    try:
        relative = path.relative_to(markdown_root_path())
    except ValueError:
        relative = path.relative_to(domain_vault_path())
    return relative.with_suffix("").as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
