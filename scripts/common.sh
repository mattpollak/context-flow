#!/usr/bin/env bash
# common.sh — Shared constants for relay plugin scripts.
# Source this at the top of every script: source "$(dirname "$0")/common.sh"

APP_NAME="relay"
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/$APP_NAME"
COUNTER_PREFIX="${TMPDIR:-/tmp}/$APP_NAME"
