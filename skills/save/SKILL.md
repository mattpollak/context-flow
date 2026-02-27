---
name: save
description: >
  Save the current workstream's state to disk.
  Trigger phrases: "save context", "save state", "save session", "persist context", "update context".
---

# Save Workstream State

Save the current session's context to the active workstream's state file.

## Data directory

```
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
```

## Steps

1. **Find active workstream.** Read `$DATA_DIR/workstreams.json` and find the workstream with `"status": "active"`. If none is active, tell the user there's no active workstream to save and suggest `/context-flow:new` or `/context-flow:switch`.

2. **Write state file.** The state file is at `$DATA_DIR/workstreams/<name>/state.md`. Write an updated version that captures the current session state. Use atomic overwrite:

   ```bash
   # Write new content to temp file first
   cat > "$DATA_DIR/workstreams/<name>/state.md.new" << 'STATEEOF'
   <content>
   STATEEOF

   # Atomic swap with backup
   [ -f "$DATA_DIR/workstreams/<name>/state.md" ] && \
     command mv "$DATA_DIR/workstreams/<name>/state.md" "$DATA_DIR/workstreams/<name>/state.md.bak"
   command mv "$DATA_DIR/workstreams/<name>/state.md.new" "$DATA_DIR/workstreams/<name>/state.md"
   ```

3. **State file content.** The state file MUST stay under 80 lines. Include these sections:

   ```markdown
   # <Workstream Name>

   ## Metadata
   - **Description:** ...
   - **Created:** YYYY-MM-DD
   - **Project dir:** /path (if applicable)

   ## Current Status
   2-3 sentences on what's happening right now.

   ## Key Decisions
   - Bullet list of important choices made (accumulated across sessions)

   ## Next Steps
   1. Numbered list of what to do next

   ## Recent Sessions (optional, if space permits)
   - YYYY-MM-DD: One-line summary
   ```

   **Priority if space is tight:** Current Status > Next Steps > Key Decisions > Recent Sessions.

4. **Update registry timestamp.** Update `last_touched` in `$DATA_DIR/workstreams.json`:
   ```bash
   jq --arg name "<name>" --arg date "$(date +%Y-%m-%d)" \
      '.workstreams[$name].last_touched = $date' \
      "$DATA_DIR/workstreams.json" > "$DATA_DIR/workstreams.json.tmp" && \
   command mv "$DATA_DIR/workstreams.json.tmp" "$DATA_DIR/workstreams.json"
   ```

5. **Reset context monitor counter.** After saving, reset the tool call counter so the context exhaustion warnings stop until the next threshold:
   ```bash
   for f in ${TMPDIR:-/tmp}/context-flow-*.count; do
     [ -f "$f" ] && echo "0" > "$f"
   done
   ```

6. **Confirm.** Tell the user the state was saved. Mention the backup file exists at `state.md.bak`.
