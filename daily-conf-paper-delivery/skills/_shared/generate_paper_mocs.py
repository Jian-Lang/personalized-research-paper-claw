#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
from pathlib import Path


_SHARED_DIR = Path(__file__).resolve().parent
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from moc_builder import build_tree_mocs
from user_config import (
    daily_mocs_dir,
    daily_project_papers_dir,
    manual_mocs_dir,
    manual_project_papers_dir,
    obsidian_vault_path,
    paths_config,
)


def main() -> int:
    summaries = {}
    exclude_dir_names = {paths_config()["concepts_folder"], "assets"}
    projects = [
        ("daily", daily_project_papers_dir(), daily_mocs_dir(), "用于浏览每日推荐项目中的论文笔记与分类入口。"),
        ("manual", manual_project_papers_dir(), manual_mocs_dir(), "用于浏览手动阅读项目中的论文笔记与分类入口。"),
    ]

    for project_name, content_root, output_root, intro in projects:
        if not content_root.parent.exists():
            summaries[project_name] = {
                "status": "skipped",
                "reason": "project-not-created-yet",
                "root_dir": str(content_root.parent),
            }
            continue
        summary = build_tree_mocs(
            vault_root=obsidian_vault_path(),
            content_root=content_root,
            output_root=output_root,
            title_prefix="论文目录页",
            intro=intro,
            exclude_dir_names=exclude_dir_names,
        )
        summaries[project_name] = summary.to_dict()

    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
