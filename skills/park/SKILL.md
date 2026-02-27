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

2. **Save state first.** Before parking, save the current state:
   a. Write updated state to `state.md.new` (under 80 lines: current status, key decisions, next steps):
      ```bash
      cat > "$DATA_DIR/workstreams/<name>/state.md.new" << 'STATEEOF'
      <content>
      STATEEOF
      ```
   b. Complete the save (rotate files, update registry, reset counter):
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/complete-save.sh" "<name>"
      ```

3. **Park the workstream.** Set status to `"parked"` in the registry:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/park-registry.sh" "<name>"
   ```

4. **Confirm.** Tell the user the workstream has been parked. Mention they can resume it later with `/context-flow:switch <name>`.
