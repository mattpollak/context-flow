#!/usr/bin/env bash
# init-data-dir.sh — Ensure the relay data directory exists.
# Idempotent: safe to call multiple times.
set -euo pipefail
source "$(dirname "$0")/common.sh"

mkdir -p "$DATA_DIR/workstreams"

if [ ! -f "$DATA_DIR/workstreams.json" ]; then
  cp "${CLAUDE_PLUGIN_ROOT}/templates/workstreams.json" "$DATA_DIR/workstreams.json"
fi
