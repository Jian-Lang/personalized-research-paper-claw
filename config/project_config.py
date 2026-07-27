#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
GLOBAL_CONFIG_PATH = REPO_ROOT / "config" / "user-config.local.json"
DELIVERY_CONFIG_PATH = (
    REPO_ROOT / "daily-conf-paper-delivery" / "skills" / "_shared" / "user-config.local.json"
)
NOTER_CONFIG_PATH = (
    REPO_ROOT / "research-paper-noter" / "skills" / "_shared" / "user-config.local.json"
)

DEFAULT_CONFIG = {
    "paths": {
        "daily_papers_folder": "DailyPapers",
        "manual_papers_folder": "PersonalizedPaper",
        "domain_papers_folder": "DomainPapers",
        "domain_paper_folder": "paper",
        "domain_content_folder": "content",
        "project_mocs_folder": "mocs",
        "project_papers_folder": "papers",
        "concepts_folder": "_concepts",
        "zotero_db": "~/Zotero/zotero.sqlite",
        "zotero_storage": "~/Zotero/storage",
    },
    "daily_papers": {
        "conferences": [
            {"name": "ICML", "year": 2026, "daily_take": 5},
            {"name": "ICLR", "year": 2026, "daily_take": 5},
            {"name": "CVPR", "year": 2026, "daily_take": 5},
            {"name": "ACL", "year": 2026, "daily_take": 5, "shuffle": True},
        ],
        "scan_limit": 1000,
        "topics": [],
        "keywords": [],
        "exclude_keywords": [],
        "min_score": 2,
    },
    "automation": {
        "auto_refresh_indexes": True,
        "git_commit": False,
        "git_push": False,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    return loaded if isinstance(loaded, dict) else {}


@lru_cache(maxsize=2)
def load_user_config(scope: str = "delivery") -> dict:
    if scope not in {"delivery", "noter"}:
        raise ValueError(f"unknown config scope: {scope}")

    config = copy.deepcopy(DEFAULT_CONFIG)
    if scope == "delivery":
        config["automation"]["daily_run_time"] = "08:00"
    delivery_config = _read_json(DELIVERY_CONFIG_PATH)
    noter_config = _read_json(NOTER_CONFIG_PATH)

    # Preserve legacy path settings while the root Markdown path is migrated.
    for legacy_config in (delivery_config, noter_config):
        if isinstance(legacy_config.get("paths"), dict):
            _deep_merge(config["paths"], legacy_config["paths"])

    if isinstance(delivery_config.get("daily_papers"), dict):
        _deep_merge(config["daily_papers"], delivery_config["daily_papers"])

    workflow_config = delivery_config if scope == "delivery" else noter_config
    if isinstance(workflow_config.get("automation"), dict):
        _deep_merge(config["automation"], workflow_config["automation"])

    # The root config is authoritative only for the shared Markdown location.
    global_config = _read_json(GLOBAL_CONFIG_PATH)
    if isinstance(global_config.get("paths"), dict):
        _deep_merge(config["paths"], global_config["paths"])
    return config


def _expand(path_value: str) -> Path:
    return Path(path_value).expanduser()


def paths_config() -> dict:
    return load_user_config()["paths"]


def daily_papers_config() -> dict:
    return load_user_config()["daily_papers"]


def automation_config(scope: str = "delivery") -> dict:
    config = load_user_config(scope)["automation"]
    if config.get("git_push") and not config.get("git_commit"):
        config = copy.deepcopy(config)
        config["git_push"] = False
    return config


def markdown_root_path() -> Path:
    env_override = os.environ.get("RESEARCH_PAPER_CLAW_MARKDOWN_ROOT") or os.environ.get(
        "RESEARCH_PAPER_CLAW_VAULT_DIR"
    )
    if env_override:
        return _expand(env_override)
    paths = paths_config()
    return _expand(paths.get("markdown_root") or paths.get("obsidian_vault") or "~/ResearchNotes")


def obsidian_vault_path() -> Path:
    """Backward-compatible alias for integrations that still use the old name."""
    return markdown_root_path()


def daily_project_dir() -> Path:
    return markdown_root_path() / paths_config().get("daily_papers_folder", "DailyPapers")


def manual_project_dir() -> Path:
    return markdown_root_path() / paths_config().get("manual_papers_folder", "PersonalizedPaper")


def domain_papers_folder_name() -> str:
    return paths_config().get("domain_papers_folder", "DomainPapers")


def domain_vault_path() -> Path:
    env_override = os.environ.get("DOMAIN_PAPERS_VAULT")
    if env_override:
        return _expand(env_override)
    paths = paths_config()
    if not paths.get("markdown_root") and paths.get("domain_papers_vault"):
        return _expand(paths["domain_papers_vault"])
    return markdown_root_path() / domain_papers_folder_name()


def domain_paper_folder_name() -> str:
    return paths_config().get("domain_paper_folder", "paper")


def domain_content_folder_name() -> str:
    return paths_config().get("domain_content_folder", "content")


def validate_domain_name(domain_name: str) -> str:
    name = str(domain_name)
    forbidden = ("/", "\\", "\x00", "\n", "\r")
    if (
        not name
        or name != name.strip()
        or name in {".", ".."}
        or any(char in name for char in forbidden)
    ):
        raise ValueError("domain must be a non-empty single folder name")
    return name


def domain_project_dir(domain_name: str) -> Path:
    return domain_vault_path() / validate_domain_name(domain_name)


def domain_project_papers_dir(domain_name: str) -> Path:
    return domain_project_dir(domain_name) / domain_paper_folder_name()


def domain_project_content_dir(domain_name: str) -> Path:
    return domain_project_dir(domain_name) / domain_content_folder_name()


def project_mocs_folder_name() -> str:
    return paths_config().get("project_mocs_folder", "mocs")


def project_papers_folder_name() -> str:
    return paths_config().get("project_papers_folder", "papers")


def daily_mocs_dir() -> Path:
    return daily_project_dir() / project_mocs_folder_name()


def daily_project_papers_dir() -> Path:
    return daily_project_dir() / project_papers_folder_name()


def manual_mocs_dir() -> Path:
    return manual_project_dir() / project_mocs_folder_name()


def manual_project_papers_dir() -> Path:
    return manual_project_dir() / project_papers_folder_name()


def ensure_daily_layout() -> None:
    daily_mocs_dir().mkdir(parents=True, exist_ok=True)
    daily_project_papers_dir().mkdir(parents=True, exist_ok=True)


def ensure_manual_layout() -> None:
    manual_mocs_dir().mkdir(parents=True, exist_ok=True)
    manual_project_papers_dir().mkdir(parents=True, exist_ok=True)


def ensure_domain_layout(domain_name: str) -> None:
    domain_project_papers_dir(domain_name).mkdir(parents=True, exist_ok=True)
    domain_project_content_dir(domain_name).mkdir(parents=True, exist_ok=True)


def daily_history_path() -> Path:
    return daily_project_dir() / ".history.json"


def manual_summary_path() -> Path:
    return manual_mocs_dir() / "PersonalizedPaperContent.md"


def daily_content_filename(target_date: date | str) -> str:
    date_str = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
    return f"DailyPaperContent-{date_str}.md"


def daily_content_path(target_date: date | str) -> Path:
    return daily_mocs_dir() / daily_content_filename(target_date)


def paper_notes_dir() -> Path:
    return daily_project_papers_dir()


def daily_papers_dir() -> Path:
    return daily_mocs_dir()


def manual_papers_dir() -> Path:
    return manual_project_dir()


def concepts_dir() -> Path:
    return daily_project_papers_dir() / paths_config().get("concepts_folder", "_concepts")


def zotero_db_path() -> Path:
    return _expand(paths_config().get("zotero_db", "~/Zotero/zotero.sqlite"))


def zotero_storage_dir() -> Path:
    return _expand(paths_config().get("zotero_storage", "~/Zotero/storage"))


def auto_refresh_indexes_enabled(scope: str = "delivery") -> bool:
    return bool(automation_config(scope)["auto_refresh_indexes"])


def git_commit_enabled(scope: str = "delivery") -> bool:
    return bool(automation_config(scope)["git_commit"])


def git_push_enabled(scope: str = "delivery") -> bool:
    return bool(automation_config(scope)["git_push"])


def daily_run_time() -> str:
    value = str(automation_config("delivery").get("daily_run_time", "08:00")).strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("automation.daily_run_time must use 24-hour HH:MM format, for example 08:00")
    return value
