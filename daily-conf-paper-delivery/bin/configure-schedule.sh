#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LABEL="com.personalized-research-paper-claw.daily-conf-paper-delivery"
TARGET_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$TARGET_DIR/$LABEL.plist"
LAUNCH_DOMAIN="gui/$(id -u)"
GLOBAL_CONFIG="$PROJECT_DIR/../config/user-config.local.json"
DAILY_CONFIG="$PROJECT_DIR/skills/_shared/user-config.local.json"
ACTION="install"
REQUESTED_TIME=""

usage() {
  printf 'Usage:\n'
  printf '  %s [--time HH:MM]\n' "$0"
  printf '  %s --status\n' "$0"
  printf '  %s --remove\n' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --time)
      [[ $# -ge 2 ]] || { echo "--time requires HH:MM." >&2; exit 2; }
      REQUESTED_TIME="$2"
      shift 2
      ;;
    --status)
      [[ "$ACTION" == "install" ]] || { echo "Choose only one of --status or --remove." >&2; exit 2; }
      ACTION="status"
      shift
      ;;
    --remove)
      [[ "$ACTION" == "install" ]] || { echo "Choose only one of --status or --remove." >&2; exit 2; }
      ACTION="remove"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$ACTION" != "install" && -n "$REQUESTED_TIME" ]]; then
  echo "--time can only be used when enabling or updating the schedule." >&2
  exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Automatic scheduling currently supports macOS launchd only." >&2
  exit 1
fi

if [[ "$ACTION" == "status" ]]; then
  if [[ -f "$TARGET_PLIST" ]] && launchctl print "$LAUNCH_DOMAIN/$LABEL" >/dev/null 2>&1; then
    STATUS_TIME="$(python3 - "$TARGET_PLIST" <<'PY'
import plistlib
import sys
from pathlib import Path

payload = plistlib.loads(Path(sys.argv[1]).read_bytes())
interval = payload.get("StartCalendarInterval", {})
print(f"{int(interval.get('Hour', 0)):02d}:{int(interval.get('Minute', 0)):02d}")
PY
)"
    echo "Daily Conf Paper Delivery is enabled for $STATUS_TIME (system local time)."
  elif [[ -f "$TARGET_PLIST" ]]; then
    echo "Daily Conf Paper Delivery has a schedule file but is not loaded."
  else
    echo "Daily Conf Paper Delivery is disabled."
  fi
  exit 0
fi

if [[ "$ACTION" == "remove" ]]; then
  launchctl bootout "$LAUNCH_DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$TARGET_PLIST"
  echo "Removed Daily Conf Paper Delivery schedule."
  exit 0
fi

if [[ ! -f "$GLOBAL_CONFIG" ]]; then
  echo "Global config not found: $GLOBAL_CONFIG" >&2
  echo "Create it from config/user-config.example.json before enabling scheduling." >&2
  exit 1
fi

if [[ ! -f "$DAILY_CONFIG" ]]; then
  echo "Daily config not found: $DAILY_CONFIG" >&2
  echo "Create it from skills/_shared/user-config.example.json and configure your interests first." >&2
  exit 1
fi

if [[ -n "$REQUESTED_TIME" ]]; then
  python3 "$PROJECT_DIR/scripts/schedule_config.py" \
    --config "$DAILY_CONFIG" \
    --time "$REQUESTED_TIME"
fi

mkdir -p "$TARGET_DIR" "$PROJECT_DIR/logs"

SCHEDULE_TIME="$({
  python3 - "$PROJECT_DIR" "$TARGET_PLIST" "$LABEL" <<'PY'
import plistlib
import sys
from pathlib import Path

project_dir = Path(sys.argv[1]).resolve()
target_plist = Path(sys.argv[2])
label = sys.argv[3]

sys.path.insert(0, str(project_dir / "skills" / "_shared"))
from user_config import daily_run_time, markdown_root_path

try:
    run_time = daily_run_time()
except ValueError as exc:
    raise SystemExit(str(exc)) from exc

hour, minute = (int(value) for value in run_time.split(":"))
runner = project_dir / "bin" / "daily-conf-paper-delivery.sh"
logs_dir = project_dir / "logs"

payload = {
    "Label": label,
    "ProgramArguments": [str(runner)],
    "WorkingDirectory": str(project_dir),
    "EnvironmentVariables": {
        "RESEARCH_PAPER_CLAW_MARKDOWN_ROOT": str(markdown_root_path()),
    },
    "StartCalendarInterval": {
        "Hour": hour,
        "Minute": minute,
    },
    "StandardOutPath": str(logs_dir / "launchd.out.log"),
    "StandardErrorPath": str(logs_dir / "launchd.err.log"),
}

target_plist.write_bytes(plistlib.dumps(payload, sort_keys=False))
print(run_time)
PY
} 2>&1)" || {
  echo "$SCHEDULE_TIME" >&2
  exit 1
}

launchctl bootout "$LAUNCH_DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$LAUNCH_DOMAIN" "$TARGET_PLIST"
launchctl enable "$LAUNCH_DOMAIN/$LABEL"

echo "Daily Conf Paper Delivery scheduled for $SCHEDULE_TIME (system local time)."
echo "Config: $DAILY_CONFIG"
echo "Plist: $TARGET_PLIST"
