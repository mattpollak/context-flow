---
name: park
description: >
  Park the current workstream (save state and deactivate).
  Trigger phrases: "park this", "park workstream", "pause workstream", "shelve this".
argument-hint: "[workstream-name]"
---

# Park Workstream

Park the active workstream (or the one named `$ARGUMENTS`), saving its state first.

## Data directory

```
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
```

## Steps

1. **Determine target.** If `$ARGUMENTS` is provided, park that workstream. Otherwise, park the currently active workstream. If no workstream is active and no name was given, tell the user and stop.

2. **Save state first.** Before parking, save the current state using the same procedure as `/context-flow:save`:
   - Write updated `state.md.new` with current status, key decisions, next steps (under 80 lines)
   - Atomic swap: `command mv state.md state.md.bak`, `command mv state.md.new state.md`

3. **Update registry.** Set the workstream's status to `"parked"` and update `last_touched`:
   ```bash
   jq --arg name "<name>" --arg date "$(date +%Y-%m-%d)" \
      '(.workstreams[$name].status = "parked") |
       (.workstreams[$name].last_touched = $date)' \
      "$DATA_DIR/workstreams.json" > "$DATA_DIR/workstreams.json.tmp" && \
   command mv "$DATA_DIR/workstreams.json.tmp" "$DATA_DIR/workstreams.json"
   ```

4. **Reset context monitor counter.** After saving, reset the tool call counter:
   ```bash
   for f in ${TMPDIR:-/tmp}/context-flow-*.count; do
     [ -f "$f" ] && echo "0" > "$f"
   done
   ```

5. **Confirm.** Tell the user the workstream has been parked. Mention they can resume it later with `/context-flow:switch <name>`.
