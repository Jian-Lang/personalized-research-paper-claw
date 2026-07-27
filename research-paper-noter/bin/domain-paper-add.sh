#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
TODAY="$(date +%F)"
LOG_FILE="$LOG_DIR/domain-paper-$TODAY.log"

export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

usage() {
  printf 'Usage:\n'
  printf '  %s "Domain" "Category/Subcategory" "Paper title or arXiv URL"\n' "$0"
  printf '  %s "Domain" "Category/Subcategory" "Title 1" "Title 2"\n' "$0"
  printf '  %s "Domain" "Category/Subcategory" /path/to/titles.txt\n' "$0"
}

if [[ $# -lt 3 ]]; then
  usage
  exit 2
fi

DOMAIN="$1"
CATEGORY_PATH="$2"
shift 2

cd "$PROJECT_DIR"

normalize_category_path() {
  CATEGORY_PATH="$(
  python3 - "$CATEGORY_PATH" <<'PY'
import sys

raw_category = sys.argv[1]
category_parts = [
    part.strip()
    for part in raw_category.replace(">", "/").split("/")
    if part.strip()
]
if not category_parts:
    raise SystemExit("category path cannot be empty")
for part in category_parts:
    if part in {".", ".."} or "\x00" in part:
        raise SystemExit(f"invalid category path part: {part!r}")
print(" / ".join(category_parts))
PY
  )"
}

resolve_paths() {
  CONFIG_VALUES=()
  while IFS= read -r value; do
    CONFIG_VALUES+=("$value")
  done < <(
  python3 - "$DOMAIN" <<'PY'
import sys

sys.path.insert(0, "skills/_shared")
from user_config import (
    domain_project_content_dir,
    domain_project_dir,
    domain_project_papers_dir,
    domain_vault_path,
    ensure_domain_layout,
)

domain = sys.argv[1]
try:
    ensure_domain_layout(domain)
except ValueError as exc:
    raise SystemExit(str(exc)) from exc

for path in (
    domain_vault_path(),
    domain_project_dir(domain),
    domain_project_papers_dir(domain),
    domain_project_content_dir(domain),
):
    print(path)
PY
  )

  if [[ ${#CONFIG_VALUES[@]} -ne 4 ]]; then
    echo "Failed to resolve Domain Paper paths." >&2
    exit 1
  fi

  DOMAIN_VAULT_DIR="${CONFIG_VALUES[0]}"
  DOMAIN_PROJECT_DIR="${CONFIG_VALUES[1]}"
  DOMAIN_PAPERS_DIR="${CONFIG_VALUES[2]}"
  DOMAIN_CONTENT_DIR="${CONFIG_VALUES[3]}"
}

normalize_category_path
resolve_paths
mkdir -p "$LOG_DIR"

PAPERS=()
if [[ $# -eq 1 && -f "$1" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "${line//[[:space:]]/}" ]] && continue
    PAPERS+=("$line")
  done < "$1"
else
  PAPERS=("$@")
fi

if [[ ${#PAPERS[@]} -eq 0 ]]; then
  echo "No paper input found." >&2
  exit 2
fi

INPUT_SPEC="$(
  printf '%s\n' "${PAPERS[@]}" | sed 's/^/- /'
)"

format_list() {
  if [[ $# -eq 0 ]]; then
    printf -- '- None\n'
    return
  fi
  printf '%s\n' "$@" | sed 's/^/- /'
}

list_domain_notes() {
  local notes_dir="$DOMAIN_PAPERS_DIR"
  if [[ ! -d "$notes_dir" ]]; then
    printf -- '- None\n'
    return
  fi
  find "$notes_dir" -maxdepth 1 -type f -name '*.md' -print \
    | sort \
    | sed "s#^$notes_dir/##; s#^#- #"
}

list_missing_domain_content_notes() {
  python3 - "$DOMAIN_PAPERS_DIR" "$DOMAIN_CONTENT_DIR/.domain-papers.json" "$CATEGORY_PATH" <<'PY'
import json
import re
import sys
from pathlib import Path

paper_dir = Path(sys.argv[1])
sidecar_path = Path(sys.argv[2])
raw_category = sys.argv[3]
category_parts = [part.strip() for part in raw_category.replace(">", "/").split("/") if part.strip()]
category_path = " / ".join(category_parts)
page_key = "/".join(category_parts) + ".md"

existing_notes = set()
if sidecar_path.exists():
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
        page_entries = data.get("pages", {}).get(page_key, {})
        if isinstance(page_entries, dict):
            for value in page_entries.values():
                if isinstance(value, dict):
                    note = str(value.get("note", "")).strip()
                    if note:
                        existing_notes.add(note)
    except json.JSONDecodeError:
        pass

frontmatter_re = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
field_re = lambda key: re.compile(rf"^{re.escape(key)}:\s*(.+)$", re.MULTILINE)

missing = []
category_notes = []
if paper_dir.exists():
    for note_path in sorted(paper_dir.glob("*.md")):
        text = note_path.read_text(encoding="utf-8")
        match = frontmatter_re.match(text)
        if not match:
            continue
        frontmatter = match.group(1)
        category_match = field_re("zotero_collection").search(frontmatter)
        title_match = field_re("title").search(frontmatter)
        if not category_match or not title_match:
            continue
        note_category = category_match.group(1).strip().strip('"').strip("'")
        if note_category != category_path:
            continue
        category_notes.append(note_path.stem)
        if note_path.stem in existing_notes:
            continue
        title = title_match.group(1).strip().strip('"').strip("'")
        missing.append(f"- {note_path.stem}.md | {title}")

if len(existing_notes) >= len(category_notes):
    print("- None")
else:
    print("\n".join(missing) if missing else "- None")
PY
}

CODEX_ARGS=(
  "${CODEX_BIN:-codex}"
  --sandbox danger-full-access
  --ask-for-approval never
  --search
  exec
  --skip-git-repo-check
  -C "$PROJECT_DIR"
  --add-dir "$DOMAIN_VAULT_DIR"
)

if [[ -n "${CODEX_MODEL:-}" ]]; then
  CODEX_ARGS+=(--model "$CODEX_MODEL")
fi

{
  SUCCESSFUL_PAPERS=()
  FAILED_PAPERS=()

  echo "[$(date '+%F %T')] start domain papers: $DOMAIN / $CATEGORY_PATH (${#PAPERS[@]} papers)"
  for i in "${!PAPERS[@]}"; do
    PAPER="${PAPERS[$i]}"
    NOTE_PROMPT="domain 论文详细笔记生成（批处理第 $((i + 1))/${#PAPERS[@]} 篇）。严格 follow 仓库 domain-papers skill 的路径规则，并调用 paper-reader 生成或复用这一篇论文的详细笔记。

本阶段只处理详细笔记，不更新 content，不运行 \`skills/domain-papers/scripts/update_domain_content.py\`。

本次运行的目标路径是固定的：
- DOMAIN_VAULT_PATH: $DOMAIN_VAULT_DIR
- DOMAIN: $DOMAIN
- CATEGORY_PATH: $CATEGORY_PATH
- DOMAIN_PROJECT_PATH: $DOMAIN_PROJECT_DIR
- DOMAIN_PAPERS_PATH: $DOMAIN_PAPERS_DIR
- DOMAIN_CONTENT_PATH: $DOMAIN_CONTENT_DIR

硬性约束：
- 只允许写入 \`$DOMAIN_PROJECT_DIR\` 下面
- 详细论文笔记只能写到 \`$DOMAIN_PAPERS_DIR\`
- 不要写入或更新 \`$DOMAIN_CONTENT_DIR\`
- 当前调用来源是 \`domain-papers\`
- TARGET_NOTES_PATH 必须是 \`$DOMAIN_PAPERS_DIR\`
- 如果已有同一论文的合格详细笔记，复用已有笔记，不重复生成

输入论文：
- $PAPER"
    echo "[$(date '+%F %T')] note $((i + 1))/${#PAPERS[@]}: $PAPER"
    if "${CODEX_ARGS[@]}" "$NOTE_PROMPT"; then
      SUCCESSFUL_PAPERS+=("$PAPER")
      echo "[$(date '+%F %T')] note success $((i + 1))/${#PAPERS[@]}: $PAPER"
    else
      FAILED_PAPERS+=("$PAPER")
      echo "[$(date '+%F %T')] note failed $((i + 1))/${#PAPERS[@]}: $PAPER"
    fi
  done

  SUCCESS_SPEC="$(format_list "${SUCCESSFUL_PAPERS[@]-}")"
  FAILURE_SPEC="$(format_list "${FAILED_PAPERS[@]-}")"
  NOTE_SPEC="$(list_domain_notes)"
  MISSING_CONTENT_NOTE_SPEC="$(list_missing_domain_content_notes)"

  echo "[$(date '+%F %T')] note summary: ${#SUCCESSFUL_PAPERS[@]} succeeded, ${#FAILED_PAPERS[@]} failed"

  if [[ ${#SUCCESSFUL_PAPERS[@]} -eq 0 ]]; then
    echo "[$(date '+%F %T')] skip domain content: no successful notes"
    echo "[$(date '+%F %T')] failed papers:"
    printf '%s\n' "$FAILURE_SPEC"
    exit 1
  fi

  CONTENT_PROMPT="domain content 汇总（批处理最后一步）。严格 follow 仓库 domain-papers skill 的 content 规则，只根据已生成或已复用的详细笔记更新 domain content。

本阶段只更新 content，不生成、不重写、不删除详细论文笔记。

本次运行的目标路径是固定的：
- DOMAIN_VAULT_PATH: $DOMAIN_VAULT_DIR
- DOMAIN: $DOMAIN
- CATEGORY_PATH: $CATEGORY_PATH
- DOMAIN_PROJECT_PATH: $DOMAIN_PROJECT_DIR
- DOMAIN_PAPERS_PATH: $DOMAIN_PAPERS_DIR
- DOMAIN_CONTENT_PATH: $DOMAIN_CONTENT_DIR

硬性约束：
- 只允许写入 \`$DOMAIN_CONTENT_DIR\`
- 不要写入或更新 \`$DOMAIN_PAPERS_DIR\`
- content 更新必须使用 \`skills/domain-papers/scripts/update_domain_content.py\`
- content 内同一子类按论文年份从新到旧排序；同一年内 arXiv 论文按 published_date 从新到旧排序，非 arXiv 或缺少完整日期的论文按标题排序
- content 条目必须复用 manual 风格，包含笔记链接、年份、Venue、论文链接、首图、摘要、问题背景、核心方法、评估和借鉴意义
- 年份和 Venue 优先从详细笔记 frontmatter 读取
- 摘要 English 直接使用论文原始 abstract，摘要中文忠实翻译
- 问题背景、核心方法、评估、借鉴意义必须基于对应详细笔记二次整理，不要机械截取笔记原文
- 只对本次输入论文传入 \`--related-work\`，在条目末尾生成 \`> **与其他工作的关系**：...\`；用几句话说明它与本次输入论文或同 domain 已有论文的承接、对比、互补关系
- 已在 content 中存在但不属于本次输入列表的旧论文，不要为了补充“与其他工作的关系”而改写或回填

原始输入论文列表如下（仅用于上下文，不代表都成功）：
$INPUT_SPEC

本次详细笔记阶段成功的论文如下。content 只能为这些论文调用 \`update_domain_content.py\`：
$SUCCESS_SPEC

本次详细笔记阶段失败的论文如下。不要为这些论文更新 content：
$FAILURE_SPEC

当前 \`$DOMAIN_PAPERS_DIR\` 下的详细笔记文件清单如下，用于把成功论文映射到 note 文件名：
$NOTE_SPEC

当前分类已存在于 \`$DOMAIN_PAPERS_DIR\`、但尚未进入当前 Gallery 页的详细笔记如下。
如果不是 \`- None\`，你必须基于这些现有详细笔记一并补全 content 条目；这一步仍然只允许更新 content，不要改动 paper：
$MISSING_CONTENT_NOTE_SPEC"
  echo "[$(date '+%F %T')] update domain content: $DOMAIN / $CATEGORY_PATH"
  CONTENT_STATUS=0
  "${CODEX_ARGS[@]}" "$CONTENT_PROMPT" || CONTENT_STATUS=$?

  echo "[$(date '+%F %T')] content status: $CONTENT_STATUS"
  echo "[$(date '+%F %T')] successful papers:"
  printf '%s\n' "$SUCCESS_SPEC"
  echo "[$(date '+%F %T')] failed papers:"
  printf '%s\n' "$FAILURE_SPEC"
  echo "[$(date '+%F %T')] done"

  if [[ $CONTENT_STATUS -ne 0 || ${#FAILED_PAPERS[@]} -ne 0 ]]; then
    exit 1
  fi
} >> "$LOG_FILE" 2>&1
