#!/usr/bin/env bash
# reset-counter.sh — Reset the context monitor tool call counter to 0.
set -euo pipefail
source "$(dirname "$0")/common.sh"

for f in "${COUNTER_PREFIX}"-*.count; do
  [ -f "$f" ] && echo "0" > "$f"
done
