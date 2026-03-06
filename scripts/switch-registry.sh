#!/usr/bin/env bash
# switch-registry.sh — Activate a workstream in the registry (does not park the old one).
# Usage: bash switch-registry.sh <new-name>
set -euo pipefail
source "$(dirname "$0")/common.sh"

NEW="${1:-}"
if [ -z "$NEW" ]; then
  echo "Usage: switch-registry.sh <new-name>" >&2
  exit 1
fi

REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
jq --arg new "$NEW" --arg date "$TODAY" \
  '(.workstreams[$new].status = "active") |
   (.workstreams[$new].last_touched = $date)' \
  "$REGISTRY" > "$REGISTRY.tmp" && \
command mv "$REGISTRY.tmp" "$REGISTRY"
