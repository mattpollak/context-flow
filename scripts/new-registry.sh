#!/usr/bin/env bash
# new-registry.sh — Add a new workstream to the registry and set it as active.
# Usage: bash new-registry.sh <name> <description> <project-dir>
set -euo pipefail
source "$(dirname "$0")/common.sh"

NAME="${1:-}"
DESC="${2:-}"
DIR="${3:-}"
if [ -z "$NAME" ]; then
  echo "Usage: new-registry.sh <name> <description> <project-dir>" >&2
  exit 1
fi

REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
jq --arg name "$NAME" \
   --arg desc "$DESC" \
   --arg date "$TODAY" \
   --arg dir "$DIR" \
   '.workstreams[$name] = {status: "active", description: $desc, created: $date, last_touched: $date, project_dir: $dir}' \
   "$REGISTRY" > "$REGISTRY.tmp" && \
command mv "$REGISTRY.tmp" "$REGISTRY"
