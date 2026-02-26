#!/usr/bin/env bash
# migrate-from-workstreams.sh — One-time migration from a manual workstream system to context-flow.
#
# Parses a WORKSTREAMS.md registry with markdown tables under ## Active, ## Parked,
# ## Completed headings, plus a ## Parking Lot bullet list. Copies each workstream's
# SESSION.md → state.md (truncated to 80 lines) and companion files.
#
# Expected WORKSTREAMS.md table format:
#   | [name](./dir/) | description | date |
#
# Expected directory layout:
#   <source-dir>/
#   ├── WORKSTREAMS.md
#   ├── <workstream-name>/
#   │   ├── SESSION.md
#   │   ├── ARCHITECTURE.md  (optional)
#   │   └── PLAN.md          (optional)
#   └── ...
#
# Non-destructive: does NOT delete old files.
#
# Usage: bash migrate-from-workstreams.sh [--dry-run] [source-dir]
#        source-dir defaults to ~/src/claude/context

set -euo pipefail

DRY_RUN=false
SOURCE_DIR=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    *) SOURCE_DIR="$arg" ;;
  esac
done

SOURCE_DIR="${SOURCE_DIR:-$HOME/src/claude/context}"
REGISTRY_FILE="$SOURCE_DIR/WORKSTREAMS.md"
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"

# Verify prerequisites
if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required. Install it: sudo apt install jq"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is required for parsing WORKSTREAMS.md"
  exit 1
fi

if [ ! -f "$REGISTRY_FILE" ]; then
  echo "ERROR: Registry not found at $REGISTRY_FILE"
  echo "Usage: bash migrate-from-workstreams.sh [--dry-run] [source-dir]"
  exit 1
fi

if [ "$DRY_RUN" = true ]; then
  echo "=== DRY RUN MODE — no files will be created or modified ==="
  echo
fi

echo "=== context-flow Migration ==="
echo "Source: $SOURCE_DIR"
echo "Target: $DATA_DIR"
echo

# Parse WORKSTREAMS.md into JSON using Python
# Outputs: {"workstreams": [...], "parking_lot": "..."}
export SOURCE_DIR REGISTRY_FILE
PARSED=$(python3 << 'PYEOF'
import re, json, sys, os

source_dir = os.environ["SOURCE_DIR"]
registry_file = os.environ["REGISTRY_FILE"]

with open(registry_file) as f:
    content = f.read()

workstreams = []
parking_lot_lines = []

# Split into sections by ## headings
sections = re.split(r'^## ', content, flags=re.MULTILINE)

for section in sections:
    if not section.strip():
        continue

    heading, _, body = section.partition('\n')
    heading = heading.strip().lower()

    if heading in ('active', 'parked', 'completed'):
        status = heading
        # Parse markdown table rows: | [name](./dir/) | description | date |
        for line in body.strip().splitlines():
            line = line.strip()
            if not line.startswith('|') or line.startswith('|---') or line.startswith('| Workstream'):
                continue
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) < 3:
                continue

            # Extract name from [name](./dir/) or plain text
            name_match = re.match(r'\[([^\]]+)\]', cols[0])
            name = name_match.group(1) if name_match else cols[0].strip()

            description = cols[1].strip()

            # Extract date (strip parenthetical session info)
            date_str = cols[2].strip()
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
            date = date_match.group(1) if date_match else date_str

            # Try to find project_dir from SESSION.md
            project_dir = None
            session_file = os.path.join(source_dir, name, "SESSION.md")
            if os.path.isfile(session_file):
                with open(session_file) as sf:
                    for sline in sf:
                        # Match patterns like:
                        #   - **Project directory:** `~/path/`
                        #   - **Repo:** ~/path/
                        #   Working directory: /path/
                        m = re.search(r'(?:Project directory|Repo|Working directory)\*{0,2}:\*{0,2}\s*`?([~/][^`\s]+)`?', sline)
                        if m:
                            path = m.group(1).strip().rstrip('/')
                            # Expand ~ to $HOME
                            if path.startswith('~'):
                                path = os.path.expanduser(path)
                            project_dir = path
                            break

            ws = {
                "name": name,
                "status": status,
                "description": description,
                "date": date,
            }
            if project_dir:
                ws["project_dir"] = project_dir
            workstreams.append(ws)

    elif heading.startswith('parking lot'):
        parking_lot_lines = [l for l in body.strip().splitlines() if l.strip()]

print(json.dumps({
    "workstreams": workstreams,
    "parking_lot": '\n'.join(parking_lot_lines)
}))
PYEOF
)

if [ -z "$PARSED" ] || [ "$PARSED" = "null" ]; then
  echo "ERROR: Failed to parse $REGISTRY_FILE"
  exit 1
fi

WS_COUNT=$(echo "$PARSED" | jq '.workstreams | length')
echo "Found $WS_COUNT workstreams in $REGISTRY_FILE"
echo

# Initialize data directory
if [ "$DRY_RUN" = false ]; then
  mkdir -p "$DATA_DIR/workstreams"
fi

# Build registry JSON and copy files
REGISTRY_JSON='{"workstreams":{}}'

for i in $(seq 0 $((WS_COUNT - 1))); do
  NAME=$(echo "$PARSED" | jq -r ".workstreams[$i].name")
  STATUS=$(echo "$PARSED" | jq -r ".workstreams[$i].status")
  DESC=$(echo "$PARSED" | jq -r ".workstreams[$i].description")
  DATE=$(echo "$PARSED" | jq -r ".workstreams[$i].date")
  PROJECT_DIR=$(echo "$PARSED" | jq -r ".workstreams[$i].project_dir // empty")

  echo "  Migrating: $NAME (status: $STATUS)"

  # Add to registry
  if [ -n "$PROJECT_DIR" ]; then
    REGISTRY_JSON=$(echo "$REGISTRY_JSON" | jq \
      --arg name "$NAME" --arg status "$STATUS" --arg desc "$DESC" \
      --arg date "$DATE" --arg dir "$PROJECT_DIR" \
      '.workstreams[$name] = {status: $status, description: $desc, created: $date, last_touched: $date, project_dir: $dir}')
  else
    REGISTRY_JSON=$(echo "$REGISTRY_JSON" | jq \
      --arg name "$NAME" --arg status "$STATUS" --arg desc "$DESC" --arg date "$DATE" \
      '.workstreams[$name] = {status: $status, description: $desc, created: $date, last_touched: $date}')
  fi

  WS_DIR="$DATA_DIR/workstreams/$NAME"
  OLD_WS_DIR="$SOURCE_DIR/$NAME"

  if [ "$DRY_RUN" = true ]; then
    echo "    Would create: $WS_DIR/"
    [ -f "$OLD_WS_DIR/SESSION.md" ] && echo "    Would copy: SESSION.md → state.md (truncated to 80 lines)"
    [ -f "$OLD_WS_DIR/ARCHITECTURE.md" ] && echo "    Would copy: ARCHITECTURE.md → architecture.md"
    [ -f "$OLD_WS_DIR/PLAN.md" ] && echo "    Would copy: PLAN.md → plan.md"
  else
    mkdir -p "$WS_DIR"

    if [ -f "$OLD_WS_DIR/SESSION.md" ]; then
      head -80 "$OLD_WS_DIR/SESSION.md" > "$WS_DIR/state.md"
      echo "    Copied: SESSION.md → state.md ($(wc -l < "$WS_DIR/state.md") lines)"
    else
      echo "    Warning: No SESSION.md found at $OLD_WS_DIR"
    fi

    if [ -f "$OLD_WS_DIR/ARCHITECTURE.md" ]; then
      cp "$OLD_WS_DIR/ARCHITECTURE.md" "$WS_DIR/architecture.md"
      echo "    Copied: ARCHITECTURE.md → architecture.md"
    fi

    if [ -f "$OLD_WS_DIR/PLAN.md" ]; then
      cp "$OLD_WS_DIR/PLAN.md" "$WS_DIR/plan.md"
      echo "    Copied: PLAN.md → plan.md"
    fi
  fi
done

echo

# Warn if multiple active workstreams detected
ACTIVE_COUNT=$(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "active")] | length')
if [ "$ACTIVE_COUNT" -gt 1 ]; then
  echo "WARNING: $ACTIVE_COUNT active workstreams found. context-flow expects at most one."
  echo "         Use /context-flow:park to park extras after migration."
  echo
fi

# Migrate parking lot
PARKING_LOT=$(echo "$PARSED" | jq -r '.parking_lot // empty')
if [ -n "$PARKING_LOT" ]; then
  echo "Migrating parking lot..."
  if [ "$DRY_RUN" = true ]; then
    echo "  Would create: $DATA_DIR/parking-lot.md"
  else
    printf "# Parking Lot\n\n%s\n" "$PARKING_LOT" > "$DATA_DIR/parking-lot.md"
    echo "  Created: $DATA_DIR/parking-lot.md"
  fi
  echo
fi

# Write registry
if [ "$DRY_RUN" = true ]; then
  echo "Would write registry:"
  echo "$REGISTRY_JSON" | jq .
else
  echo "$REGISTRY_JSON" | jq . > "$DATA_DIR/workstreams.json"
  echo "Wrote registry: $DATA_DIR/workstreams.json"
fi

echo
echo "=== Migration Summary ==="
echo
echo "Workstreams migrated: $WS_COUNT"
echo "  Active: $ACTIVE_COUNT"
echo "  Parked: $(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "parked")] | length')"
echo "  Completed: $(echo "$REGISTRY_JSON" | jq '[.workstreams | to_entries[] | select(.value.status == "completed")] | length')"
echo
echo "=== Post-Migration Steps ==="
echo
echo "1. Verify the migrated data:"
echo "   cat $DATA_DIR/workstreams.json"
echo "   ls $DATA_DIR/workstreams/"
echo
echo "2. Install the context-flow plugin:"
echo "   claude plugin add <path-to-context-flow-repo>"
echo
echo "3. Remove old hooks that conflict with the plugin (if any):"
echo "   - Check ~/.claude/settings.json for PreCompact / SessionEnd hooks"
echo "   - Check ~/.claude/hooks/ for session-end scripts"
echo "   - Check ~/.claude/rules/ for workstream management rules"
echo
echo "4. Old files are preserved at: $SOURCE_DIR"
echo "   Delete them when you're confident the migration is correct."
echo
