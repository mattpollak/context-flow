#!/usr/bin/env bash
# switch-registry.sh — Park old workstream and activate new one in the registry.
# Usage: bash switch-registry.sh <old-name> <new-name>
set -euo pipefail
source "$(dirname "$0")/common.sh"

OLD="${1:-}"
NEW="${2:-}"
if [ -z "$OLD" ] || [ -z "$NEW" ]; then
  echo "Usage: switch-registry.sh <old-name> <new-name>" >&2
  exit 1
fi

REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
jq --arg old "$OLD" --arg new "$NEW" --arg date "$TODAY" \
  '(.workstreams[$old].status = "parked") |
   (.workstreams[$old].last_touched = $date) |
   (.workstreams[$new].status = "active") |
   (.workstreams[$new].last_touched = $date)' \
  "$REGISTRY" > "$REGISTRY.tmp" && \
command mv "$REGISTRY.tmp" "$REGISTRY"
