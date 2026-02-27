#!/usr/bin/env bash
# park-registry.sh — Set a workstream's status to parked in the registry.
# Usage: bash park-registry.sh <workstream-name>
set -euo pipefail

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "Usage: park-registry.sh <workstream-name>" >&2
  exit 1
fi

DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
jq --arg name "$NAME" --arg date "$TODAY" \
  '(.workstreams[$name].status = "parked") |
   (.workstreams[$name].last_touched = $date)' \
  "$REGISTRY" > "$REGISTRY.tmp" && \
command mv "$REGISTRY.tmp" "$REGISTRY"
