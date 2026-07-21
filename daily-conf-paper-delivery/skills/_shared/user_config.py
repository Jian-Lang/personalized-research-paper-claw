#!/usr/bin/env python3

import sys
from pathlib import Path


_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"
if str(_CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(_CONFIG_DIR))

import project_config as _project_config  # noqa: E402
from project_config import *  # noqa: F401,F403,E402


def load_user_config() -> dict:
    return _project_config.load_user_config("delivery")


def automation_config() -> dict:
    return _project_config.automation_config("delivery")


def auto_refresh_indexes_enabled() -> bool:
    return _project_config.auto_refresh_indexes_enabled("delivery")


def git_commit_enabled() -> bool:
    return _project_config.git_commit_enabled("delivery")


def git_push_enabled() -> bool:
    return _project_config.git_push_enabled("delivery")
