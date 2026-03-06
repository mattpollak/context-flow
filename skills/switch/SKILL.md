---
name: switch
description: >
  Switch to a different workstream, saving the current one first.
  Also handles "resume workstream", "load workstream", "work on <name>".
argument-hint: "<workstream-name>"
---

# Switch Workstream

Switch this session from the current workstream to the one named `$ARGUMENTS`. Both workstreams stay active — use `/relay:park` to explicitly deactivate one.

## Steps

1. **Parse arguments.** The target workstream name is `$ARGUMENTS`. If empty, read the registry and list available (non-active) workstreams, then ask the user which one to switch to:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams.json"
   ```

2. **Validate target exists.** Check that `$ARGUMENTS` exists in the registry output. If not, list available workstreams and stop.

3. **Save current workstream.** If this session is attached to a workstream (check the `relay:` line in your session context):
   a. Write updated state to `state.md.new` (under 80 lines: current status, key decisions, next steps):
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/write-data-file.sh" "workstreams/<current-name>/state.md.new" << 'STATEEOF'
      <content>
      STATEEOF
      ```
   b. Complete the save (rotate files, update registry, reset counter):
      ```bash
      bash "${CLAUDE_PLUGIN_ROOT}/scripts/complete-save.sh" "<current-name>"
      ```

4. **Write session hint.** Write a session hint file for the workstream being switched away from (same format and guidelines as in `/relay:save` Step 5). Use `date -u +%Y-%m-%dT%H%M%SZ` for the timestamp and the session ID from the `relay-session-id:` line in your session context.

5. **Activate target workstream.** Ensure the target is active in the registry (handles the case where it's parked):
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/switch-registry.sh" "<new-name>"
   ```

6. **Attach to target.** Write session marker and load state:
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/attach-workstream.sh" "<new-name>" "<session-id>"
   ```

7. **Load supplementary files.** Check for optional files (skip any that return `NOT_FOUND`):
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams/<name>/plan.md"
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/read-data-file.sh" "workstreams/<name>/architecture.md"
   ```

8. **Change directory.** If the target workstream has a `project_dir` set in the registry and that directory exists, tell the user: "This workstream's project directory is `<path>`. You may want to `cd` there."

9. **Summarize.** Tell the user what workstream is now active and give a brief summary of its current status from state.md.
