#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REBUILD_SCRIPT="$PROJECT_DIR/skills/domain-papers/scripts/rebuild_domain_gallery.py"

usage() {
  printf 'Usage:\n'
  printf '  %s "Domain"\n' "$0"
  printf '  %s "Domain" "Category/Subcategory"\n' "$0"
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 2
fi

DOMAIN="$1"
shift

ARGS=(python3 "$REBUILD_SCRIPT" --domain "$DOMAIN")
if [[ $# -eq 1 ]]; then
  ARGS+=(--category-path "$1")
fi

exec "${ARGS[@]}"
