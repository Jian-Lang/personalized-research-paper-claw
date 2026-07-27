#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_DIR="$(
  python3 - "$PROJECT_DIR" <<'PY'
import sys
from pathlib import Path

project_dir = Path(sys.argv[1])
sys.path.insert(0, str(project_dir / "skills" / "_shared"))
from user_config import ensure_daily_layout, markdown_root_path

ensure_daily_layout()
print(markdown_root_path())
PY
)"
LOG_DIR="$PROJECT_DIR/logs"
TODAY="$(date +%F)"
LOG_FILE="$LOG_DIR/daily-paper-$TODAY.log"
LOCK_DIR="/tmp/daily-conf-paper-delivery.lock"

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$LOG_DIR"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(date '+%F %T')] skip daily papers: another run is in progress" >> "$LOG_FILE"
  exit 0
fi

cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}

trap cleanup EXIT

cd "$PROJECT_DIR"

{
  echo "[$(date '+%F %T')] start daily papers"
  "${CODEX_BIN:-codex}" \
    -c sandbox_workspace_write.network_access=true \
    --sandbox workspace-write \
    --ask-for-approval never \
    --search \
    exec \
    --skip-git-repo-check \
    -C "$PROJECT_DIR" \
    --add-dir "$VAULT_DIR" \
    "今日论文推荐。严格 follow 仓库 daily-papers skill 定义的全局 Markdown 根目录、格式和按需目录规则。当前项目使用会议论文源，只运行抓取和摘要式点评，不自动生成细粒度论文笔记。"
  echo "[$(date '+%F %T')] done"
} >> "$LOG_FILE" 2>&1
