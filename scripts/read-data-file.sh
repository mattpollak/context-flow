#!/usr/bin/env bash
# read-data-file.sh — Read a file from the relay data directory.
# Usage: bash read-data-file.sh <filename>
# Examples:
#   bash read-data-file.sh workstreams.json
#   bash read-data-file.sh parking-lot.md
set -euo pipefail
source "$(dirname "$0")/common.sh"

FILENAME="${1:-}"
if [ -z "$FILENAME" ]; then
  echo "Usage: read-data-file.sh <filename>" >&2
  exit 1
fi

FILE="$DATA_DIR/$FILENAME"

if [ -f "$FILE" ]; then
  cat "$FILE"
else
  echo "NOT_FOUND"
fi
