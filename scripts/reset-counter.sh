#!/usr/bin/env bash
# reset-counter.sh — Reset the context monitor tool call counter to 0.
set -euo pipefail

for f in "${TMPDIR:-/tmp}"/context-flow-*.count; do
  [ -f "$f" ] && echo "0" > "$f"
done
