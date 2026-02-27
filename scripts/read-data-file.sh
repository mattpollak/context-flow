#!/usr/bin/env bash
# read-data-file.sh — Read a file from the context-flow data directory.
# Usage: bash read-data-file.sh <filename>
# Examples:
#   bash read-data-file.sh workstreams.json
#   bash read-data-file.sh parking-lot.md
set -euo pipefail

FILENAME="${1:-}"
if [ -z "$FILENAME" ]; then
  echo "Usage: read-data-file.sh <filename>" >&2
  exit 1
fi

DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
FILE="$DATA_DIR/$FILENAME"

if [ -f "$FILE" ]; then
  cat "$FILE"
else
  echo "NOT_FOUND"
fi
