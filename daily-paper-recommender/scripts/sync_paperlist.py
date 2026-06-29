#!/usr/bin/env python3
"""
Sync selected accepted-paper JSONL files from ronpay/paperlist into this repo.

Daily recommendations read the local snapshot under data/paperlist so ordering
and de-duplication stay reproducible. Run this script only when refreshing the
accepted-paper source.
"""

from __future__ import annotations

import json
import hashlib
import random
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / "skills" / "_shared" / "user-config.local.json"
DATA_DIR = PROJECT_DIR / "data" / "paperlist"
DEFAULT_REPO_URL = "https://github.com/ronpay/paperlist.git"
DEFAULT_CACHE_DIR = Path("/private/tmp/ronpay-paperlist")


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


def run(args: list[str], cwd: Path | None = None) -> None:
    completed = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def ensure_repo(repo_url: str, cache_dir: Path) -> None:
    if (cache_dir / ".git").exists():
        run(["git", "-C", str(cache_dir), "pull", "--ff-only"])
        return
    if cache_dir.exists():
        raise SystemExit(f"Cache path exists but is not a git repo: {cache_dir}")
    run(["git", "clone", "--depth", "1", repo_url, str(cache_dir)])


def shuffled_jsonl(raw: str, conference: str, year: int) -> str:
    lines = [line for line in raw.splitlines() if line.strip()]
    seed_text = f"{conference.upper()}-{year}-paperlist-jsonl-v1"
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest(), 16)
    random.Random(seed).shuffle(lines)
    return "\n".join(lines) + "\n"


def sync_file(cache_dir: Path, conference: dict) -> Path:
    name = str(conference.get("name", "")).strip().upper()
    year = int(conference.get("year", 0) or 0)
    if not name or not year:
        raise SystemExit(f"Invalid conference config: {conference}")

    rel_path = Path(name) / f"{name.lower()}_{year}.jsonl"
    source_path = cache_dir / rel_path
    if not source_path.exists():
        raise SystemExit(f"Missing upstream file: {source_path}")
    target_path = DATA_DIR / rel_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if conference.get("shuffle"):
        raw = source_path.read_text(encoding="utf-8")
        target_path.write_text(shuffled_jsonl(raw, name, year), encoding="utf-8")
    else:
        shutil.copy2(source_path, target_path)
    return target_path


def main() -> int:
    repo_url = DEFAULT_REPO_URL
    cache_dir = DEFAULT_CACHE_DIR
    ensure_repo(repo_url, cache_dir)
    synced = []
    for conference in load_conferences():
        synced.append(sync_file(cache_dir, conference))
    for path in synced:
        print(path.relative_to(PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
