#!/usr/bin/env bash
# migrate-data.sh — One-time migration from context-flow data paths to relay.
# Moves ~/.config/context-flow/ → ~/.config/relay/
# Moves ~/.local/share/context-flow/ → ~/.local/share/relay/ (search index)
#
# Safe to run multiple times — skips if old directory doesn't exist or new one already does.
#
# Usage: bash migrate-data.sh
set -euo pipefail

OLD_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
NEW_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/relay"
OLD_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/context-flow"
NEW_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/relay"

echo "=== relay data migration ==="
echo

# Check preconditions
if [ ! -d "$OLD_CONFIG" ] && [ ! -d "$OLD_DATA" ]; then
  echo "Nothing to migrate — no context-flow data found."
  echo "  Checked: $OLD_CONFIG"
  echo "  Checked: $OLD_DATA"
  exit 0
fi

if [ -d "$NEW_CONFIG" ]; then
  echo "ERROR: Target directory already exists: $NEW_CONFIG"
  echo "       If you want to re-run migration, remove it first."
  exit 1
fi

if [ -d "$NEW_DATA" ]; then
  echo "ERROR: Target directory already exists: $NEW_DATA"
  echo "       If you want to re-run migration, remove it first."
  exit 1
fi

# Migrate config (workstreams, registry, session markers)
if [ -d "$OLD_CONFIG" ]; then
  echo "Moving config: $OLD_CONFIG → $NEW_CONFIG"
  mv "$OLD_CONFIG" "$NEW_CONFIG"
  echo "  Done."
else
  echo "No config directory to migrate ($OLD_CONFIG does not exist)"
fi

echo

# Migrate data (search index)
if [ -d "$OLD_DATA" ]; then
  echo "Moving search index: $OLD_DATA → $NEW_DATA"
  mv "$OLD_DATA" "$NEW_DATA"
  echo "  Done."
else
  echo "No search index to migrate ($OLD_DATA does not exist)"
fi

echo
echo "=== Migration complete ==="
echo
echo "Also clean up counter files:"
echo "  rm -f ${TMPDIR:-/tmp}/context-flow-*.count"
echo
