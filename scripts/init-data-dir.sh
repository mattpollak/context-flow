#!/usr/bin/env bash
# init-data-dir.sh — Ensure the context-flow data directory exists.
# Idempotent: safe to call multiple times.
set -euo pipefail

DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"

mkdir -p "$DATA_DIR/workstreams"

if [ ! -f "$DATA_DIR/workstreams.json" ]; then
  cp "${CLAUDE_PLUGIN_ROOT}/templates/workstreams.json" "$DATA_DIR/workstreams.json"
fi
