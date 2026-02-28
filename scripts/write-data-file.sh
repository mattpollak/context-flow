#!/usr/bin/env bash
# write-data-file.sh — Write content from stdin to a file in the data directory.
# Usage: echo "content" | bash write-data-file.sh <relative-path>
# Or:   bash write-data-file.sh <relative-path> << 'EOF'
#       content
#       EOF
set -euo pipefail
source "$(dirname "$0")/common.sh"

RELPATH="${1:-}"
if [ -z "$RELPATH" ]; then
  echo "Usage: write-data-file.sh <relative-path>" >&2
  exit 1
fi

FILE="$DATA_DIR/$RELPATH"

# Ensure parent directory exists
mkdir -p "$(dirname "$FILE")"

# Read from stdin and write
cat > "$FILE"

echo "Wrote: $FILE"
