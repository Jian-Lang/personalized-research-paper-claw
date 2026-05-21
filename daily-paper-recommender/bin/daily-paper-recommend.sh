#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VAULT_DIR="${RESEARCH_PAPER_CLAW_VAULT_DIR:-$HOME/ObsidianVault}"
LOG_DIR="$PROJECT_DIR/logs"
TODAY="$(date +%F)"
LOG_FILE="$LOG_DIR/daily-paper-$TODAY.log"
LOCK_DIR="/tmp/daily-paper-recommend.lock"

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
    --sandbox danger-full-access \
    --ask-for-approval never \
    --search \
    exec \
    --skip-git-repo-check \
    -C "$PROJECT_DIR" \
    --add-dir "$VAULT_DIR" \
    "今日论文推荐。严格 follow 仓库 daily-papers skill 定义的 Obsidian vault 路径、格式、目录。当前项目使用会议论文源，只运行抓取和摘要式点评，不自动生成细粒度论文笔记。"
  echo "[$(date '+%F %T')] done"
} >> "$LOG_FILE" 2>&1
