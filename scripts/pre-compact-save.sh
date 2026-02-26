#!/usr/bin/env bash
# pre-compact-save.sh — PreCompact hook: instruct Claude to save state before context compression.
# MUST exit 0 to avoid blocking compaction.
set -euo pipefail
trap 'exit 0' ERR

DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
REGISTRY="$DATA_DIR/workstreams.json"

# Check jq and registry exist
if ! command -v jq &>/dev/null || [ ! -f "$REGISTRY" ]; then
  echo "IMPORTANT: Context compaction is about to occur. If you are tracking work in a workstream, save your state now."
  exit 0
fi

# Find active workstream
ACTIVE_NAME=$(jq -r '[.workstreams | to_entries[] | select(.value.status == "active")] | first | .key // empty' "$REGISTRY" 2>/dev/null || true)

if [ -z "$ACTIVE_NAME" ]; then
  exit 0
fi

STATE_FILE="$DATA_DIR/workstreams/$ACTIVE_NAME/state.md"

cat <<EOF
IMPORTANT: Context compaction is imminent. You MUST save the active workstream '${ACTIVE_NAME}' state NOW.

Write an updated state file to: ${STATE_FILE}

Use atomic overwrite:
1. Write content to ${STATE_FILE}.new
2. mv ${STATE_FILE} ${STATE_FILE}.bak (if exists)
3. mv ${STATE_FILE}.new ${STATE_FILE}

The state file must be under 80 lines and include:
- Current status (what was being worked on)
- Key decisions made
- Next steps
- Any blockers or important context that would be lost

Also update last_touched in ${REGISTRY} using:
jq --arg name "${ACTIVE_NAME}" --arg date "\$(date +%Y-%m-%d)" '.workstreams[\$name].last_touched = \$date' "${REGISTRY}" > "${REGISTRY}.tmp" && mv "${REGISTRY}.tmp" "${REGISTRY}"
EOF

exit 0
