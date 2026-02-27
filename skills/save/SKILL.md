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

2. **Write state file.** Write the updated state to a `.new` temp file:

   ```bash
   cat > "$DATA_DIR/workstreams/<name>/state.md.new" << 'STATEEOF'
   <content>
   STATEEOF
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

4. **Complete the save.** Rotate files, update registry, and reset the context monitor — all in one step:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/complete-save.sh" "<name>"
   ```

5. **Confirm.** Tell the user the state was saved. Mention the backup file exists at `state.md.bak`.
