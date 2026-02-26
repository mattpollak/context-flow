#!/usr/bin/env bash
# context-monitor.sh — PostToolUse hook: track tool call count and warn on context exhaustion.
# Uses a counter file in $TMPDIR keyed by session_id.
# MUST exit 0 to avoid blocking tool use.
set -euo pipefail
trap 'exit 0' ERR

# Read stdin for session_id
INPUT=$(cat)

# Check jq is available — degrade gracefully
if ! command -v jq &>/dev/null; then
  exit 0
fi

SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
if [ -z "$SESSION_ID" ]; then
  exit 0
fi

COUNTER_FILE="${TMPDIR:-/tmp}/context-flow-${SESSION_ID}.count"

# Increment counter atomically
if [ -f "$COUNTER_FILE" ]; then
  COUNT=$(cat "$COUNTER_FILE" 2>/dev/null || echo "0")
  COUNT=$((COUNT + 1))
else
  COUNT=1
fi
echo "$COUNT" > "$COUNTER_FILE"

# Graduated warnings
if [ "$COUNT" -ge 100 ] && [ $((COUNT % 3)) -eq 0 ]; then
  # Critical: every 3rd call after 100
  jq -n '{
    "systemMessage": "CRITICAL: ~100+ tool calls this session. Context compaction is likely imminent. Save your workstream state NOW with /context-flow:save before context is compressed and you lose session details."
  }'
elif [ "$COUNT" -ge 80 ] && [ $((COUNT % 5)) -eq 0 ]; then
  # Warning: every 5th call after 80
  jq -n '{
    "systemMessage": "WARNING: ~80+ tool calls this session. Context window is filling up. Consider saving workstream state with /context-flow:save soon."
  }'
fi

exit 0
