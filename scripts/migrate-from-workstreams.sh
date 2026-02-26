#!/usr/bin/env bash
# migrate-from-workstreams.sh — One-time migration from manual workstream system to context-flow.
# Non-destructive: does NOT delete old files.
#
# Usage: bash migrate-from-workstreams.sh [--dry-run]

set -euo pipefail

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
  echo "=== DRY RUN MODE — no files will be created or modified ==="
  echo
fi

# Paths
OLD_DIR="$HOME/src/claude/context"
OLD_REGISTRY="$OLD_DIR/WORKSTREAMS.md"
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
REGISTRY="$DATA_DIR/workstreams.json"

# Verify prerequisites
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required. Install it: sudo apt install jq"
  exit 1
fi

if [ ! -f "$OLD_REGISTRY" ]; then
  echo "ERROR: Old registry not found at $OLD_REGISTRY"
  exit 1
fi

echo "=== context-flow Migration ==="
echo "Source: $OLD_DIR"
echo "Target: $DATA_DIR"
echo

# Initialize data directory
if [ "$DRY_RUN" = false ]; then
  mkdir -p "$DATA_DIR/workstreams"
fi

# Start building the registry JSON
REGISTRY_JSON='{"workstreams":{}}'

# Function to add a workstream to the registry and copy files
migrate_workstream() {
  local name="$1"
  local status="$2"
  local description="$3"
  local last_touched="$4"
  local project_dir="${5:-}"

  echo "  Migrating: $name (status: $status)"

  local ws_dir="$DATA_DIR/workstreams/$name"
  local old_ws_dir="$OLD_DIR/$name"

  # Add to registry JSON
  if [ -n "$project_dir" ]; then
    REGISTRY_JSON=$(echo "$REGISTRY_JSON" | jq \
      --arg name "$name" \
      --arg status "$status" \
      --arg desc "$description" \
      --arg date "$last_touched" \
      --arg dir "$project_dir" \
      '.workstreams[$name] = {status: $status, description: $desc, created: $date, last_touched: $date, project_dir: $dir}')
  else
    REGISTRY_JSON=$(echo "$REGISTRY_JSON" | jq \
      --arg name "$name" \
      --arg status "$status" \
      --arg desc "$description" \
      --arg date "$last_touched" \
      '.workstreams[$name] = {status: $status, description: $desc, created: $date, last_touched: $date}')
  fi

  if [ "$DRY_RUN" = true ]; then
    echo "    Would create: $ws_dir/"
    [ -f "$old_ws_dir/SESSION.md" ] && echo "    Would copy: SESSION.md → state.md (truncated to 80 lines)"
    [ -f "$old_ws_dir/ARCHITECTURE.md" ] && echo "    Would copy: ARCHITECTURE.md → architecture.md"
    [ -f "$old_ws_dir/PLAN.md" ] && echo "    Would copy: PLAN.md → plan.md"
    return
  fi

  mkdir -p "$ws_dir"

  # Copy SESSION.md → state.md (truncated to 80 lines)
  if [ -f "$old_ws_dir/SESSION.md" ]; then
    head -80 "$old_ws_dir/SESSION.md" > "$ws_dir/state.md"
    echo "    Copied: SESSION.md → state.md ($(wc -l < "$ws_dir/state.md") lines)"
  else
    echo "    Warning: No SESSION.md found at $old_ws_dir"
  fi

  # Copy companion files if they exist
  if [ -f "$old_ws_dir/ARCHITECTURE.md" ]; then
    cp "$old_ws_dir/ARCHITECTURE.md" "$ws_dir/architecture.md"
    echo "    Copied: ARCHITECTURE.md → architecture.md"
  fi

  if [ -f "$old_ws_dir/PLAN.md" ]; then
    cp "$old_ws_dir/PLAN.md" "$ws_dir/plan.md"
    echo "    Copied: PLAN.md → plan.md"
  fi
}

# Migrate known workstreams
# (Hardcoded based on current WORKSTREAMS.md — this is a one-time script)
echo "Migrating workstreams..."

migrate_workstream "squadkeeper" "active" \
  "SquadKeeper — mobile-first PWA for coaching staff: practice stats, player development, team logistics" \
  "2026-02-26" \
  "/home/matt/src/personal/squadkeeper"

migrate_workstream "context-flow" "active" \
  "Claude Code plugin — workstream management, context persistence, session history" \
  "2026-02-26" \
  "/home/matt/src/personal/context-flow"

migrate_workstream "local-wsl-environment" "parked" \
  "Local WSL development environment setup and configuration" \
  "2026-02-15"

migrate_workstream "game-tracking" "completed" \
  "Game Tracking feature — live scoring, play-by-play, lineups, derived stats. All 5 phases + UX review." \
  "2026-02-25" \
  "/home/matt/src/personal/squadkeeper"

migrate_workstream "setup-test" "completed" \
  "Testing the workstream management system" \
  "2026-02-18"

# Note: context-flow should be the only active one after migration
# Fix: park squadkeeper since we can only have one active
REGISTRY_JSON=$(echo "$REGISTRY_JSON" | jq '.workstreams["squadkeeper"].status = "parked"')

echo

# Extract parking lot
echo "Migrating parking lot..."
PARKING_LOT_CONTENT=$(sed -n '/^## Parking Lot/,/^## /{ /^## Parking Lot/d; /^## /d; p; }' "$OLD_REGISTRY" | sed '/^$/d')

if [ -n "$PARKING_LOT_CONTENT" ]; then
  if [ "$DRY_RUN" = true ]; then
    echo "  Would create: $DATA_DIR/parking-lot.md"
  else
    {
      echo "# Parking Lot"
      echo
      echo "$PARKING_LOT_CONTENT"
    } > "$DATA_DIR/parking-lot.md"
    echo "  Created: $DATA_DIR/parking-lot.md"
  fi
else
  echo "  No parking lot entries found"
fi

echo

# Write registry
if [ "$DRY_RUN" = true ]; then
  echo "Would write registry:"
  echo "$REGISTRY_JSON" | jq .
else
  echo "$REGISTRY_JSON" | jq . > "$REGISTRY"
  echo "Wrote registry: $REGISTRY"
fi

echo
echo "=== Migration Summary ==="
echo
echo "Workstreams migrated: $(echo "$REGISTRY_JSON" | jq '.workstreams | length')"
echo "  Active: $(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "active")] | length')"
echo "  Parked: $(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "parked")] | length')"
echo "  Completed: $(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "completed")] | length')"
echo
echo "=== Manual Cleanup Steps ==="
echo
echo "After verifying the migration, remove the old hooks and rules:"
echo
echo "1. Remove old PreCompact + SessionEnd hooks from ~/.claude/settings.json:"
echo '   Edit the file and delete the "PreCompact" and "SessionEnd" entries from the "hooks" object.'
echo
echo "2. Remove old workstream rules:"
echo "   rm ~/.claude/rules/workstreams.md"
echo
echo "3. Remove old session-end hook script:"
echo "   rm ~/.claude/hooks/session-end-snapshot.sh"
echo
echo "4. Enable the context-flow plugin in Claude Code:"
echo '   Add to ~/.claude/settings.json under "enabledPlugins":'
echo '   "context-flow@local": true'
echo "   Or install with: claude plugin add ~/src/personal/context-flow"
echo
echo "5. Old files are preserved at: $OLD_DIR"
echo "   Delete them when you're confident the migration is correct."
echo
