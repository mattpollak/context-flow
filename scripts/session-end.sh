#!/usr/bin/env bash
# session-end.sh — SessionEnd hook: cleanup temp files and update timestamp.
# Claude can't act on output from this hook (session is over).
# MUST exit 0 to avoid blocking session end.
set -euo pipefail
trap 'exit 0' ERR

# Read stdin for session_id
INPUT=$(cat)

# Check jq is available
if ! command -v jq &>/dev/null; then
  exit 0
fi

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)

# Clean up counter file
if [ -n "$SESSION_ID" ]; then
  rm -f "${TMPDIR:-/tmp}/context-flow-${SESSION_ID}.count"
fi

# Update last_touched on active workstream
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
REGISTRY="$DATA_DIR/workstreams.json"

if [ ! -f "$REGISTRY" ]; then
  exit 0
fi

ACTIVE_NAME=$(jq -r '[.workstreams | to_entries[] | select(.value.status == "active")] | first | .key // empty' "$REGISTRY" 2>/dev/null || true)

if [ -n "$ACTIVE_NAME" ]; then
  TODAY=$(date +%Y-%m-%d)
  jq --arg name "$ACTIVE_NAME" --arg date "$TODAY" \
    '.workstreams[$name].last_touched = $date' \
    "$REGISTRY" > "$REGISTRY.tmp" 2>/dev/null && \
  mv "$REGISTRY.tmp" "$REGISTRY" 2>/dev/null || true
fi

exit 0
