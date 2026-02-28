#!/usr/bin/env bash
# approve-scripts.sh — PreToolUse hook that auto-approves Bash commands
# running context-flow plugin scripts. Receives plugin root as $1 and
# tool call JSON on stdin.
set -euo pipefail

PLUGIN_ROOT="${1:-}"
if [ -z "$PLUGIN_ROOT" ]; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Check if the first line of the command runs a script from this plugin
FIRST_LINE=$(echo "$COMMAND" | head -1)
if echo "$FIRST_LINE" | grep -qF "$PLUGIN_ROOT/scripts/" 2>/dev/null; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"context-flow plugin script"}}'
fi
exit 0
