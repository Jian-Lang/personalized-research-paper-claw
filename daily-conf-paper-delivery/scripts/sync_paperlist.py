#!/usr/bin/env python3
"""Import configured conference JSONL snapshots from a compatible local directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / "skills" / "_shared" / "user-config.local.json"
DATA_DIR = PROJECT_DIR / "data" / "paperlist"


def load_conferences() -> list[dict]:
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        conferences = config.get("daily_papers", {}).get("conferences", [])
    else:
        conferences = [
            {"name": "ICML", "year": 2026, "daily_take": 5},
            {"name": "ICLR", "year": 2026, "daily_take": 5},
            {"name": "CVPR", "year": 2026, "daily_take": 5},
            {"name": "ACL", "year": 2026, "daily_take": 5},
        ]
    if isinstance(conferences, dict):
        conferences = [conferences]
    return [c for c in conferences if isinstance(c, dict) and c.get("enabled", True)]


def shuffled_jsonl(raw: str, conference: str, year: int) -> str:
    lines = [line for line in raw.splitlines() if line.strip()]
    seed_text = f"{conference.upper()}-{year}-paperlist-jsonl-v1"
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16)
    random.Random(seed).shuffle(lines)
    return "\n".join(lines) + "\n"


def validate_jsonl(raw: str, source_path: Path) -> None:
    paper_count = 0
    for line_no, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            paper = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSONL in {source_path}, line {line_no}: {exc}") from exc
        if not isinstance(paper, dict):
            raise SystemExit(f"Expected an object in {source_path}, line {line_no}")
        if not str(paper.get("title", "")).strip():
            raise SystemExit(f"Missing title in {source_path}, line {line_no}")
        if not str(paper.get("abstract", "")).strip():
            raise SystemExit(f"Missing abstract in {source_path}, line {line_no}")
        paper_count += 1
    if paper_count == 0:
        raise SystemExit(f"No papers found in {source_path}")


def sync_file(source_dir: Path, conference: dict) -> Path:
    name = str(conference.get("name", "")).strip().upper()
    year = int(conference.get("year", 0) or 0)
    if not name or not year:
        raise SystemExit(f"Invalid conference config: {conference}")

    rel_path = Path(name) / f"{name.lower()}_{year}.jsonl"
    source_path = source_dir / rel_path
    if not source_path.exists():
        raise SystemExit(f"Missing source file: {source_path}")

    raw = source_path.read_text(encoding="utf-8")
    validate_jsonl(raw, source_path)

    target_path = DATA_DIR / rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if conference.get("shuffle"):
        raw = shuffled_jsonl(raw, name, year)
    elif raw and not raw.endswith("\n"):
        raw += "\n"
    target_path.write_text(raw, encoding="utf-8")
    return target_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import configured conference snapshots from a local paperlist directory."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Directory containing <CONF>/<conf>_<year>.jsonl files",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.expanduser().resolve()
    if not source_dir.is_dir():
        parser.error(f"source directory does not exist: {source_dir}")

    synced = [sync_file(source_dir, conference) for conference in load_conferences()]
    for path in synced:
        print(path.relative_to(PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
