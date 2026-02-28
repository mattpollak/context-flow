#!/usr/bin/env bash
# complete-save.sh — Rotate state files, update registry, and reset counter.
# Called after the state.md.new file has been written.
# Usage: bash complete-save.sh <workstream-name>
set -euo pipefail
source "$(dirname "$0")/common.sh"

NAME="${1:-}"
if [ -z "$NAME" ]; then
  echo "Usage: complete-save.sh <workstream-name>" >&2
  exit 1
fi

STATE_DIR="$DATA_DIR/workstreams/$NAME"
STATE_FILE="$STATE_DIR/state.md"

# Validate workstream name format
if ! [[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Invalid workstream name: $NAME" >&2
  exit 1
fi

# 1. Rotate state files: .new -> current (with .bak backup)
if [ -f "$STATE_FILE.new" ]; then
  [ -f "$STATE_FILE" ] && command mv "$STATE_FILE" "$STATE_FILE.bak"
  command mv "$STATE_FILE.new" "$STATE_FILE"
else
  echo "No state.md.new found at $STATE_DIR" >&2
  exit 1
fi

# 2. Update registry last_touched
REGISTRY="$DATA_DIR/workstreams.json"
if [ -f "$REGISTRY" ]; then
  TODAY=$(date +%Y-%m-%d)
  jq --arg name "$NAME" --arg date "$TODAY" \
    '.workstreams[$name].last_touched = $date' \
    "$REGISTRY" > "$REGISTRY.tmp" && \
  command mv "$REGISTRY.tmp" "$REGISTRY"
fi

# 3. Reset context monitor counter
for f in "${COUNTER_PREFIX}"-*.count; do
  [ -f "$f" ] && echo "0" > "$f"
done

echo "Saved: $STATE_FILE (backup: state.md.bak)"
