#!/usr/bin/env bash
# session-start.sh — SessionStart hook: load active workstream context.
# Outputs JSON with additionalContext for Claude to see.
# MUST exit 0 to avoid blocking the session.
set -euo pipefail
trap 'exit 0' ERR

DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
REGISTRY="$DATA_DIR/workstreams.json"

# Initialize data directory (idempotent)
bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-data-dir.sh" 2>/dev/null || true

# Check jq is available
if ! command -v jq &>/dev/null; then
  cat <<'ENDJSON'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "context-flow: WARNING — jq is not installed. Install jq to enable workstream management. See: https://jqlang.github.io/jq/download/"
  }
}
ENDJSON
  exit 0
fi

# Check registry exists
if [ ! -f "$REGISTRY" ]; then
  exit 0
fi

# Find active workstream
ACTIVE_NAME=$(jq -r '[.workstreams | to_entries[] | select(.value.status == "active")] | first | .key // empty' "$REGISTRY" 2>/dev/null || true)

if [ -z "$ACTIVE_NAME" ]; then
  # List available workstreams
  AVAILABLE=$(jq -r '[.workstreams | to_entries[] | select(.value.status == "parked") | .key] | join(", ")' "$REGISTRY" 2>/dev/null || true)
  if [ -n "$AVAILABLE" ]; then
    CONTEXT="context-flow: No active workstream. Parked workstreams: ${AVAILABLE}. Use /context-flow:switch to resume one, or /context-flow:new to create one."
  else
    CONTEXT="context-flow: No workstreams found. Use /context-flow:new to create one."
  fi
else
  STATE_FILE="$DATA_DIR/workstreams/$ACTIVE_NAME/state.md"
  if [ -f "$STATE_FILE" ]; then
    STATE_CONTENT=$(cat "$STATE_FILE")
    CONTEXT=$(printf "context-flow: Active workstream '%s'\n---\n%s\n---" "$ACTIVE_NAME" "$STATE_CONTENT")
  else
    CONTEXT="context-flow: Active workstream '${ACTIVE_NAME}' (no state file found — use /context-flow:save to create one)"
  fi
fi

# Output as JSON with additionalContext
# Use jq to safely encode the context string
jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
