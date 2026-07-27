#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
TODAY="$(date +%F)"
LOG_FILE="$LOG_DIR/manual-paper-$TODAY.log"

resolve_paths() {
  CONFIG_VALUES=()
  while IFS= read -r value; do
    CONFIG_VALUES+=("$value")
  done < <(
  python3 - "$PROJECT_DIR" <<'PY'
import sys
from pathlib import Path

project_dir = Path(sys.argv[1])
sys.path.insert(0, str(project_dir / "skills" / "_shared"))
from user_config import (
    ensure_manual_layout,
    manual_mocs_dir,
    manual_project_dir,
    manual_project_papers_dir,
    manual_summary_path,
    markdown_root_path,
)

ensure_manual_layout()
for path in (
    markdown_root_path(),
    manual_project_dir(),
    manual_mocs_dir(),
    manual_project_papers_dir(),
    manual_summary_path(),
):
    print(path)
PY
  )

  if [[ ${#CONFIG_VALUES[@]} -ne 5 ]]; then
    echo "Failed to resolve the global Markdown root and Personalized paths." >&2
    exit 1
  fi

  VAULT_DIR="${CONFIG_VALUES[0]}"
  MANUAL_PROJECT_DIR="${CONFIG_VALUES[1]}"
  MANUAL_MOCS_DIR="${CONFIG_VALUES[2]}"
  MANUAL_PAPERS_DIR="${CONFIG_VALUES[3]}"
  MANUAL_SUMMARY_FILE="${CONFIG_VALUES[4]}"
}

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

usage() {
  printf 'Usage:\n'
  printf '  %s "Paper title or arXiv URL"\n' "$0"
  printf '  %s "Title 1" "Title 2"\n' "$0"
  printf '  %s /path/to/titles.txt\n' "$0"
}

if [[ $# -eq 0 ]]; then
  usage
  exit 2
fi

resolve_paths

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

if [[ $# -eq 1 && -f "$1" ]]; then
  INPUT_SPEC="输入文件: $1"
else
  INPUT_SPEC="$(
    printf '%s\n' "$@" | sed 's/^/- /'
  )"
fi

PROMPT="手动论文阅读。严格 follow 仓库 manual-papers skill：逐篇生成 paper-reader 详细笔记，并追加到 PersonalizedPaperContent；汇总页不要今日锐评和分流表，只按主题追加新增论文，不改已有内容。

本次运行的目标路径是固定的，必须严格使用：
- MANUAL_PROJECT_PATH: $MANUAL_PROJECT_DIR
- MANUAL_MOCS_PATH: $MANUAL_MOCS_DIR
- MANUAL_NOTES_PATH: $MANUAL_PAPERS_DIR
- MANUAL_SUMMARY_PATH: $MANUAL_SUMMARY_FILE

硬性约束：
- 只允许写入 \`$MANUAL_PROJECT_DIR\` 下面
- 汇总文件只能写到 \`$MANUAL_SUMMARY_FILE\`
- 论文笔记只能写到 \`$MANUAL_PAPERS_DIR\` 下的子目录

输入如下：
$INPUT_SPEC"

CODEX_ARGS=(
  "${CODEX_BIN:-codex}"
  -c
  sandbox_workspace_write.network_access=true
  --sandbox workspace-write
  --ask-for-approval never
  --search
  exec
  --skip-git-repo-check
  -C "$PROJECT_DIR"
  --add-dir "$VAULT_DIR"
)

if [[ -n "${CODEX_MODEL:-}" ]]; then
  CODEX_ARGS+=(--model "$CODEX_MODEL")
fi

{
  echo "[$(date '+%F %T')] start manual papers"
  "${CODEX_ARGS[@]}" "$PROMPT"
  echo "[$(date '+%F %T')] done"
} >> "$LOG_FILE" 2>&1
