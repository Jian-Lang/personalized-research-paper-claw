#!/usr/bin/env python3

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from datetime import date


DEFAULT_CONFIG = {
    "paths": {
        "obsidian_vault": "~/ObsidianVault",
        "paper_notes_folder": "论文笔记",
        "daily_papers_folder": "DailyPapers",
        "manual_papers_folder": "PersonalizedPaper",
        "domain_papers_vault": "~/DomainPaperVault",
        "domain_paper_folder": "paper",
        "domain_content_folder": "content",
        "project_mocs_folder": "mocs",
        "project_papers_folder": "papers",
        "concepts_folder": "_概念",
        "zotero_db": "~/Zotero/zotero.sqlite",
        "zotero_storage": "~/Zotero/storage",
    },
    "daily_papers": {
        "keywords": [
            "world model",
            "diffusion model",
            "embodied ai",
            "3d gaussian splatting",
            "4d gaussian splatting",
            "sim-to-real",
            "sim2real",
            "robot simulation",
        ],
        "negative_keywords": [
            "medical imaging",
            "weather forecast",
            "climate",
            "pet restoration",
            "mri",
            "ct scan",
            "pathology",
            "diagnosis",
            "protein",
            "drug discovery",
            "molecular",
            "audio generation",
            "music generation",
            "speech synthesis",
            "text-to-speech",
            "speech recognition",
            "voice cloning",
            "coding agent",
            "code agent",
            "code generation",
            "software engineering agent",
            "gui agent",
            "computer use",
            "web agent",
            "browser agent",
            "document parsing",
            "document understanding",
            "ocr",
            "rag framework",
            "retrieval augmented",
            "retrieval-augmented",
            "llm memory",
            "long-term memory for llm",
            "text-to-sql",
            "code repair",
            "code review",
            "trading",
            "financial",
        ],
        "domain_boost_keywords": [
            "robot",
            "manipulation",
            "grasping",
            "locomotion",
            "navigation",
            "planning",
            "reinforcement learning",
            "policy learning",
            "visuomotor",
            "action prediction",
        ],
        "arxiv_categories": ["cs.RO", "cs.CV", "cs.AI", "cs.LG"],
        "min_score": 2,
        "top_n": 30,
        "single_day_max_age_days": 21,
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


@lru_cache(maxsize=1)
def load_user_config() -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config_dir = Path(__file__).resolve().parent
    config_path = config_dir / "user-config.local.json"
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        if isinstance(loaded, dict):
            _deep_merge(config, loaded)

    return config


def _expand(path_value: str) -> Path:
    return Path(path_value).expanduser()


def paths_config() -> dict:
    return load_user_config()["paths"]


def daily_papers_config() -> dict:
    return load_user_config()["daily_papers"]


def automation_config() -> dict:
    config = load_user_config()["automation"]
    if config.get("git_push") and not config.get("git_commit"):
        config = copy.deepcopy(config)
        config["git_push"] = False
    return config


def obsidian_vault_path() -> Path:
    return _expand(paths_config()["obsidian_vault"])


def daily_project_dir() -> Path:
    return obsidian_vault_path() / paths_config()["daily_papers_folder"]


def manual_project_dir() -> Path:
    return obsidian_vault_path() / paths_config().get("manual_papers_folder", "PersonalizedPaper")


def domain_vault_path() -> Path:
    env_override = os.environ.get("DOMAIN_PAPERS_VAULT")
    if env_override:
        return _expand(env_override)
    return _expand(paths_config().get("domain_papers_vault", str(obsidian_vault_path())))


def domain_paper_folder_name() -> str:
    return paths_config().get("domain_paper_folder", "paper")


def domain_content_folder_name() -> str:
    return paths_config().get("domain_content_folder", "content")


def domain_project_dir(domain_name: str) -> Path:
    return domain_vault_path() / domain_name


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


def daily_history_path() -> Path:
    return daily_project_dir() / ".history.json"


def manual_summary_path() -> Path:
    return manual_mocs_dir() / "PersonalizedPaperContent.md"


def daily_content_filename(target_date: date | str) -> str:
    if isinstance(target_date, date):
        date_str = target_date.isoformat()
    else:
        date_str = str(target_date)
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
    return daily_project_papers_dir() / paths_config()["concepts_folder"]


def zotero_db_path() -> Path:
    return _expand(paths_config()["zotero_db"])


def zotero_storage_dir() -> Path:
    return _expand(paths_config()["zotero_storage"])


def auto_refresh_indexes_enabled() -> bool:
    return bool(automation_config()["auto_refresh_indexes"])


def git_commit_enabled() -> bool:
    return bool(automation_config()["git_commit"])


def git_push_enabled() -> bool:
    return bool(automation_config()["git_push"])
