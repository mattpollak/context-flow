#!/usr/bin/env bash
# update-registry.sh — Update last_touched for a workstream in the registry.
# Usage: bash update-registry.sh <workstream-name>
set -euo pipefail
source "$(dirname "$0")/common.sh"

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "Usage: update-registry.sh <workstream-name>" >&2
  exit 1
fi

REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 0
fi

TODAY=$(date +%Y-%m-%d)
jq --arg name "$NAME" --arg date "$TODAY" \
  '.workstreams[$name].last_touched = $date' \
  "$REGISTRY" > "$REGISTRY.tmp" && \
command mv "$REGISTRY.tmp" "$REGISTRY"
