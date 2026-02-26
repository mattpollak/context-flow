---
name: switch
description: >
  Switch to a different workstream, saving the current one first.
  Also handles "resume workstream", "load workstream", "work on <name>".
argument-hint: "<workstream-name>"
---

# Switch Workstream

Switch from the current active workstream to the one named `$ARGUMENTS`.

## Data directory

```
DATA_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/context-flow"
```

## Steps

1. **Parse arguments.** The target workstream name is `$ARGUMENTS`. If empty, read `$DATA_DIR/workstreams.json` and list available (non-active) workstreams, then ask the user which one to switch to.

2. **Validate target exists.** Check that `$ARGUMENTS` exists in `$DATA_DIR/workstreams.json`. If not, list available workstreams and stop.

3. **Save current workstream.** If there is an active workstream:
   a. Determine its state file path: `$DATA_DIR/workstreams/<active-name>/state.md`
   b. Write an updated `state.md` using atomic overwrite:
      - Write current status, key decisions, and next steps to `state.md.new`
      - `mv state.md state.md.bak` (if state.md exists)
      - `mv state.md.new state.md`
   c. Keep the content under 80 lines. Include: current status (what was being worked on), key decisions made this session, next steps.
   d. Set the old workstream's status to `"parked"` and update `last_touched` in the registry.

4. **Activate target workstream.** Set its status to `"active"` and update `last_touched` in the registry using jq:
   ```bash
   jq --arg old "<old-name>" --arg new "<new-name>" --arg date "$(date +%Y-%m-%d)" \
      '(.workstreams[$old].status = "parked") |
       (.workstreams[$old].last_touched = $date) |
       (.workstreams[$new].status = "active") |
       (.workstreams[$new].last_touched = $date)' \
      "$DATA_DIR/workstreams.json" > "$DATA_DIR/workstreams.json.tmp" && \
   mv "$DATA_DIR/workstreams.json.tmp" "$DATA_DIR/workstreams.json"
   ```

5. **Load target context.** Read and display the target workstream's files:
   - **Always read:** `$DATA_DIR/workstreams/<name>/state.md`
   - **Read if exists:** `$DATA_DIR/workstreams/<name>/plan.md`
   - **Read if exists:** `$DATA_DIR/workstreams/<name>/architecture.md`

6. **Change directory.** If the target workstream has a `project_dir` set in the registry and that directory exists, tell the user: "This workstream's project directory is `<path>`. You may want to `cd` there."

7. **Summarize.** Tell the user what workstream is now active and give a brief summary of its current status from state.md.
