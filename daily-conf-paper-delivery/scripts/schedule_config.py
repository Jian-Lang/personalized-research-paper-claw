#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Optional


TIME_PATTERN = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")


def set_daily_run_time(config_path: Path, run_time: str) -> bool:
    if not TIME_PATTERN.fullmatch(run_time):
        raise ValueError("daily run time must use 24-hour HH:MM format, for example 08:00")
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Daily config not found: {config_path}. Create it from user-config.example.json first."
        )

    with config_path.open("r", encoding="utf-8") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValueError("Daily config must contain a JSON object")

    automation = config.setdefault("automation", {})
    if not isinstance(automation, dict):
        raise ValueError("automation must contain a JSON object")
    if automation.get("daily_run_time") == run_time:
        return False
    automation["daily_run_time"] = run_time

    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=config_path.parent,
            prefix=f".{config_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            temporary_path = Path(stream.name)
        os.chmod(temporary_path, config_path.stat().st_mode)
        os.replace(temporary_path, config_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Update the Daily scheduling time safely.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--time", required=True)
    args = parser.parse_args()

    try:
        changed = set_daily_run_time(args.config, args.time)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    state = "Updated" if changed else "Kept"
    print(f"{state} Daily schedule time at {args.time}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
