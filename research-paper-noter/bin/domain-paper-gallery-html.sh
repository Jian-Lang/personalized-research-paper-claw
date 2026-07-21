#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
EXPORT_SCRIPT="$PROJECT_DIR/skills/domain-papers/scripts/export_domain_gallery_html.py"

usage() {
  printf 'Usage:\n'
  printf '  %s "Domain"\n' "$0"
  printf '  %s "Domain" "Category/Subcategory"\n' "$0"
  printf '  %s "Domain" ["Category/Subcategory"] --output /path/to/gallery.html\n' "$0"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

DOMAIN="$1"
shift

ARGS=(python3 "$EXPORT_SCRIPT" --domain "$DOMAIN")
if [[ $# -gt 0 && "$1" != --* ]]; then
  ARGS+=(--category-path "$1")
  shift
fi

exec "${ARGS[@]}" "$@"
